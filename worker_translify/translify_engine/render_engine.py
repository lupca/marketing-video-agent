import os
import gc
import asyncio
import logging
import subprocess
import shutil
import cv2
import numpy as np
import soundfile as sf
import pyrubberband as pyrb
from PIL import Image

from model.video_schema import VideoProject, Scene
from translify_engine.phase3_compose import tts_generate_segment
from translify_engine.subtitle_utils import segments_to_ass

logger = logging.getLogger(__name__)

def clean_gpu_memory():
    """Aggressively release GPU memory"""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except ImportError:
        pass

import os
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["FLAGS_fraction_of_gpu_memory_to_use"] = "0.05"

def _get_perframe_text_detector():
    """Lazily initialize and cache a PaddleOCR text detection model (det-only, no recognition)."""
    if not hasattr(_get_perframe_text_detector, "_instance"):
        from shared_core.gpu_utils import detect_torch_device
        
        # --- MONKEYPATCH FOR PADDLEPADDLE VERSION MISMATCH & GRAPH OPTIMIZATION SEGFAULTS ---
        import paddle.inference as inference
        if not hasattr(inference.Config, '_monkeypatched'):
            original_config_init = inference.Config.__init__
            def patched_config_init(self, *args, **kwargs):
                original_config_init(self, *args, **kwargs)
                try:
                    self.switch_ir_optim(False)
                    self.delete_pass("fc_fuse_pass")
                    self.delete_pass("fc_elementwise_layernorm_fuse_pass")
                except Exception as e:
                    logger.warning(f"Paddle Config patch error: {e}")
            inference.Config.__init__ = patched_config_init
            
            # Patch set_optimization_level to avoid missing attribute crash
            if not hasattr(inference.Config, 'set_optimization_level'):
                inference.Config.set_optimization_level = lambda self, level: None
                
            # Intercept switch_ir_optim to force it to always be False
            original_switch_ir_optim = inference.Config.switch_ir_optim
            def patched_switch_ir_optim(self, x=False):
                try:
                    original_switch_ir_optim(self, False)
                except Exception as e:
                    logger.warning(f"Paddle switch_ir_optim patch error: {e}")
            inference.Config.switch_ir_optim = patched_switch_ir_optim
            
            inference.Config._monkeypatched = True
            logger.info("Monkeypatched paddle.inference.Config to disable buggy IR passes and force ir_optim=False.")
        # ------------------------------------------------------------------------------------
        
        from paddleocr import PaddleOCR
        
        device = detect_torch_device()
        use_gpu = True if device == "cuda" else False
        logger.info(f"Initializing per-frame PaddleOCR detector on device={device} (use_gpu={use_gpu})...")
        
        instance = PaddleOCR(
            use_angle_cls=False,
            lang="ch",
            use_gpu=use_gpu,
            device="gpu" if use_gpu else "cpu",
            enable_mkldnn=False if use_gpu else True,
            rec=False,
            ocr_version="PP-OCRv4",
            det_db_box_thresh=0.5,
            det_db_thresh=0.3,
            det_db_unclip_ratio=1.5,
            ir_optim=False
        )
        
        # Dry run to verify GPU/cuDNN compatibility
        if use_gpu:
            try:
                import numpy as np
                dummy_img = np.zeros((32, 32, 3), dtype=np.uint8)
                instance.ocr(dummy_img, rec=False)
                logger.info("PaddleOCR GPU dry run successful in render engine!")
            except Exception as dry_err:
                logger.warning(f"PaddleOCR GPU dry run failed in render engine (likely missing cuDNN): {dry_err}. Falling back to CPU...")
                use_gpu = False
                instance = PaddleOCR(
                    use_angle_cls=False,
                    lang="ch",
                    use_gpu=False,
                    device="cpu",
                    enable_mkldnn=True,
                    rec=False,
                    ocr_version="PP-OCRv4",
                    det_db_box_thresh=0.5,
                    det_db_thresh=0.3,
                    det_db_unclip_ratio=1.5,
                    ir_optim=False
                )
        _get_perframe_text_detector._instance = instance
    return _get_perframe_text_detector._instance


def detect_text_masks_perframe(frames: list, width: int, height: int, scene_id: str) -> list:
    """
    Run PaddleOCR text detection on every frame to generate pixel-perfect masks.
    Applies temporal smoothing (union of ±1 neighboring frames) to prevent flickering.
    
    Returns list of single-channel uint8 masks (same length as frames).
    """
    import tempfile
    
    ocr = _get_perframe_text_detector()
    n = len(frames)
    
    logger.info(f"[{scene_id}] Running per-frame text detection on {n} frames...")
    
    # Phase 1: Detect text polygons on each frame
    raw_masks = []
    for i, frame in enumerate(frames):
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # Run PaddleOCR detection model directly on the in-memory numpy array (no disk writes/reads)
        try:
            result = ocr.ocr(frame, rec=False)
            
            if result and result[0]:
                polys_list = result[0]
                
                for poly in polys_list:
                    if poly is None or len(poly) < 3:
                        continue
                    pts = np.array(poly, dtype=np.int32).reshape((-1, 1, 2))
                    cv2.fillPoly(mask, [pts], 255)
        except Exception as det_err:
            logger.warning(f"[{scene_id}] Det error on frame {i}: {det_err}")
        
        raw_masks.append(mask)
    
    # Phase 2: Temporal smoothing — union of ±1 neighboring frame masks
    logger.info(f"[{scene_id}] Applying temporal mask smoothing (±1 frame union)...")
    smoothed_masks = []
    for i in range(n):
        combined = raw_masks[i].copy()
        if i > 0:
            combined = cv2.bitwise_or(combined, raw_masks[i - 1])
        if i < n - 1:
            combined = cv2.bitwise_or(combined, raw_masks[i + 1])
        smoothed_masks.append(combined)
    
    # Phase 3: Apply generous dilation for anti-aliased text edges & drop shadows
    kernel = np.ones((11, 11), np.uint8)
    dilated_masks = []
    for mask in smoothed_masks:
        dilated = cv2.dilate(mask, kernel, iterations=2)
        dilated_masks.append(dilated)
    
    text_frame_count = sum(1 for m in dilated_masks if np.any(m > 0))
    logger.info(f"[{scene_id}] Per-frame detection complete: {text_frame_count}/{n} frames have text masks.")
    
    return dilated_masks


def _inpaint_scene_clip_inprocess(scene_mp4: str, scene: Scene, output_mp4: str, fps: float, width: int, height: int, work_dir: str) -> str:
    """
    Remove hardcoded Chinese text from this specific scene clip using per-frame text detection + SOTA ProPainter inpainting.
    """
    if not scene.visual.ocr_text:
        return scene_mp4

    logger.info(f"[{scene.id}] Inpainting text using per-frame detection + ProPainter...")
    
    # 1. Read all frames from the scene video clip
    cap = cv2.VideoCapture(scene_mp4)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    
    if not frames:
        return scene_mp4
    
    # 2. Run per-frame text detection to generate pixel-perfect masks
    masks = detect_text_masks_perframe(frames, width, height, scene.id)
    
    has_any_mask = any(np.any(m > 0) for m in masks)
    
    # 3. Apply ProPainter video inpainting if we have any masked text
    if has_any_mask:
        # High-performance, low-RAM ProPainter inference scale:
        image_resize_ratio = 0.5
        max_dim = max(height, width)
        if max_dim >= 1920:
            image_resize_ratio = 0.4
        elif max_dim >= 3840:
            image_resize_ratio = 0.2

        logger.info(f"[{scene.id}] Invoking SOTA ProPainter on {len(frames)} frames with scale {image_resize_ratio}...")
        from translify_engine.propainter_inpaint import inpaint_video_frames_propainter
        inpainted_frames = inpaint_video_frames_propainter(
            frames=frames,
            masks=masks,
            work_dir=work_dir,
            image_resize_ratio=image_resize_ratio,
            mask_dilation=4
        )
    else:
        logger.info(f"[{scene.id}] No text detected in any frame. Copying original frames.")
        inpainted_frames = frames

    # 4. Write all frames to temporary MP4
    temp_raw = os.path.join(work_dir, f"{scene.id}_inpainted_raw.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(temp_raw, fourcc, fps, (width, height))
    for f in inpainted_frames:
        writer.write(f)
    writer.release()
    
    # Transcode to standard h264 mp4
    ffmpeg_bin = shutil.which("ffmpeg")
    cmd = [
        ffmpeg_bin, "-y",
        "-i", temp_raw,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-an",
        output_mp4
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_mp4

def inpaint_scene_clip(scene_mp4: str, scene: Scene, output_mp4: str, fps: float, width: int, height: int, work_dir: str) -> str:
    """Runs inpaint_scene_clip in an isolated subprocess to prevent CPU RAM accumulation."""
    import sys
    import json
    
    if not scene.visual.ocr_text:
        return scene_mp4
        
    logger.info(f"[{scene.id}] Spawning isolated subprocess for inpaint_scene_clip...")
    scene_json = os.path.join(work_dir, f"{scene.id}_data.json")
    with open(scene_json, "w", encoding="utf-8") as f:
        f.write(scene.model_dump_json(indent=2))
        
    cmd = [
        sys.executable,
        "-m", "translify_engine.cli_scene_inpaint",
        "--scene-mp4", scene_mp4,
        "--scene-data-json", scene_json,
        "--fps", str(fps),
        "--width", str(width),
        "--height", str(height),
        "--work-dir", work_dir,
        "--output-mp4", output_mp4
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    try: os.remove(scene_json)
    except: pass
    
    if proc.returncode != 0:
        logger.error(f"[{scene.id}] Subprocess inpaint_scene_clip failed with code {proc.returncode}")
        logger.error(f"Subprocess stderr: {proc.stderr}")
        logger.error(f"Subprocess stdout: {proc.stdout}")
        # Fallback to in-process
        return _inpaint_scene_clip_inprocess(scene_mp4, scene, output_mp4, fps, width, height, work_dir)
        
    return output_mp4


class RenderEngine:
    def __init__(self, voice_name: str = "vi-VN-NamMinhNeural"):
        self.voice_name = voice_name

    def render(self, project: VideoProject, original_video: str, work_dir: str, output_path: str, bgm_file: str = None) -> str:
        """
        Render each scene independently based on the VideoProject database and concatenate them.
        """
        logger.info("=== Starting Scene-Based Render Engine ===")
        os.makedirs(work_dir, exist_ok=True)
        
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise FileNotFoundError("FFmpeg not found in path")
            
        # Get video metadata
        cap = cv2.VideoCapture(original_video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        
        # 1. Slice full video original audio & BGM or use custom BGM file
        if bgm_file and os.path.exists(bgm_file):
            logger.info(f"Slicing ambient BGM from custom audio file: {bgm_file}")
            full_audio_wav = os.path.join(work_dir, "custom_bgm.wav")
            subprocess.run([
                ffmpeg_bin, "-y", "-i", bgm_file, "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", full_audio_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            logger.info("Slicing ambient BGM from original video audio track")
            full_audio_wav = os.path.join(work_dir, "full_audio.wav")
            subprocess.run([
                ffmpeg_bin, "-y", "-i", original_video, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", full_audio_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        scene_files = []
        
        for scene in project.scenes:
            logger.info(f"--- Rendering Scene: {scene.id} [{scene.start}s - {scene.end}s] ---")
            scene_dir = os.path.join(work_dir, scene.id)
            os.makedirs(scene_dir, exist_ok=True)
            
            scene_dur = round(scene.end - scene.start, 2)
            if scene_dur <= 0:
                continue
                
            # Check if this scene has already been successfully rendered in the current high-quality run
            scene_final_mp4 = os.path.join(scene_dir, "scene_final.mp4")
            if os.path.exists(scene_final_mp4) and os.path.getsize(scene_final_mp4) > 0:
                mtime = os.path.getmtime(scene_final_mp4)
                import datetime
                dt = datetime.datetime.fromtimestamp(mtime)
                # The high-quality run started on May 21, 2026 after 21:00 (local +07 time)
                cutoff = datetime.datetime(2026, 5, 21, 20, 0, 0)
                if dt > cutoff:
                    logger.info(f"[{scene.id}] Already rendered in the high-quality run ({dt}). Reusing {scene_final_mp4}")
                    scene_files.append(scene_final_mp4)
                    continue
                else:
                    logger.info(f"[{scene.id}] Found stale rendering from {dt}. Will re-render.")
            
            # a. Cut scene video clip (without audio)
            scene_raw_mp4 = os.path.join(scene_dir, "raw_clip.mp4")
            subprocess.run([
                ffmpeg_bin, "-y",
                "-ss", str(scene.start),
                "-to", str(scene.end),
                "-i", original_video,
                "-c:v", "libx264",
                "-preset", "superfast",
                "-crf", "18",
                "-an",
                scene_raw_mp4
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # b. Text inpainting
            scene_clean_mp4 = os.path.join(scene_dir, "clean_clip.mp4")
            if scene.visual.ocr_text:
                inpaint_scene_clip(scene_raw_mp4, scene, scene_clean_mp4, fps, width, height, scene_dir)
            else:
                shutil.copy(scene_raw_mp4, scene_clean_mp4)
                
            # c. Voiceover generation (TTS)
            scene_voice_wav = os.path.join(scene_dir, "voice.wav")
            sample_rate = 16000
            
            vi_text = scene.audio.vi_text.strip() if scene.audio.vi_text else ""
            if vi_text:
                temp_mp3 = os.path.join(scene_dir, "tts.mp3")
                temp_wav = os.path.join(scene_dir, "tts.wav")
                
                try:
                    success = asyncio.run(tts_generate_segment(vi_text, temp_mp3, voice=self.voice_name))
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    success = loop.run_until_complete(tts_generate_segment(vi_text, temp_mp3, voice=self.voice_name))
                    
                if success and os.path.exists(temp_mp3) and os.path.getsize(temp_mp3) > 0:
                    subprocess.run([
                        ffmpeg_bin, "-y", "-i", temp_mp3, "-ar", str(sample_rate), "-ac", "1", temp_wav
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    
                    # Timing alignment co-stretching using rubberband
                    data, sr = sf.read(temp_wav)
                    actual_dur = len(data) / sr
                    ratio = actual_dur / scene_dur
                    ratio = max(0.5, min(2.0, ratio))
                    
                    if abs(ratio - 1.0) > 0.05:
                        logger.info(f"[{scene.id}] Time-stretching voice by factor {ratio:.2f} to fit {scene_dur:.2f}s")
                        try:
                            data_stretched = pyrb.time_stretch(data, sr, ratio)
                        except Exception as e:
                            logger.error(f"Rubberband failed: {e}. Fallback to original pitch.")
                            data_stretched = data
                    else:
                        data_stretched = data
                        
                    # Cap/pad to exact duration
                    target_len = int(scene_dur * sample_rate)
                    if len(data_stretched) > target_len:
                        data_stretched = data_stretched[:target_len]
                    elif len(data_stretched) < target_len:
                        pad = np.zeros(target_len - len(data_stretched))
                        data_stretched = np.concatenate([data_stretched, pad])
                        
                    sf.write(scene_voice_wav, data_stretched, sample_rate)
                else:
                    # Fallback silent audio
                    sf.write(scene_voice_wav, np.zeros(int(scene_dur * sample_rate)), sample_rate)
            else:
                # Fallback silent audio
                sf.write(scene_voice_wav, np.zeros(int(scene_dur * sample_rate)), sample_rate)
                
            # d. Slice scene background/ambient music from separated BGM or full audio
            scene_bgm_wav = os.path.join(scene_dir, "bgm_slice.wav")
            subprocess.run([
                ffmpeg_bin, "-y",
                "-ss", str(scene.start),
                "-to", str(scene.end),
                "-i", full_audio_wav,
                "-acodec", "pcm_s16le",
                scene_bgm_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # e. Mix vocal and BGM/ambient
            scene_mixed_wav = os.path.join(scene_dir, "mixed.wav")
            filter_complex = "[1:a]volume=0.3[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]"
            subprocess.run([
                ffmpeg_bin, "-y",
                "-i", scene_voice_wav,
                "-i", scene_bgm_wav,
                "-filter_complex", filter_complex,
                "-map", "[aout]",
                "-acodec", "pcm_s16le",
                scene_mixed_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # f. Burn micro-subtitles
            scene_final_mp4 = os.path.join(scene_dir, "scene_final.mp4")
            
            if vi_text:
                subtitle_ass = os.path.join(scene_dir, "scene_subtitle.ass")
                segments_to_ass([{"start": 0.0, "end": scene_dur, "text": vi_text}], subtitle_ass)
                
                cmd = [
                    ffmpeg_bin, "-y",
                    "-i", scene_clean_mp4,
                    "-i", scene_mixed_wav,
                    "-vf", f"ass={subtitle_ass}",
                    "-c:v", "libx264",
                    "-preset", "superfast",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-shortest",
                    scene_final_mp4
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            else:
                # Mux without subtitle burn
                subprocess.run([
                    ffmpeg_bin, "-y",
                    "-i", scene_clean_mp4,
                    "-i", scene_mixed_wav,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-shortest",
                    scene_final_mp4
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                
            scene_files.append(scene_final_mp4)
            
        # 5. Concatenate all scene clips
        concat_txt = os.path.join(work_dir, "concat_list.txt")
        with open(concat_txt, "w") as f:
            for file_path in scene_files:
                abs_path = os.path.abspath(file_path)
                f.write(f"file '{abs_path}'\n")
                
        logger.info("Concatenating all processed scenes into final output video...")
        subprocess.run([
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "20",
            "-c:a", "aac",
            "-movflags", "+faststart",
            output_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        
        logger.info(f"🎉 Rendering completed! Final video saved to: {output_path}")
        return output_path
