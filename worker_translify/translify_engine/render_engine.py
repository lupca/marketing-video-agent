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

def inpaint_scene_clip(scene_mp4: str, scene: Scene, output_mp4: str, fps: float, width: int, height: int, work_dir: str) -> str:
    """
    Remove hardcoded Chinese text from this specific scene clip using OpenCV inpainting.
    """
    if not scene.visual.ocr_text:
        return scene_mp4

    logger.info(f"[{scene.id}] Inpainting text in scene clip...")
    cap = cv2.VideoCapture(scene_mp4)
    
    temp_raw = os.path.join(work_dir, f"{scene.id}_inpainted_raw.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(temp_raw, fourcc, fps, (width, height))
    
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Time relative to the scene clip
        sec_rel = frame_idx / fps
        # Absolute time in full video
        sec_abs = scene.start + sec_rel
        
        # Check for active text detections within +/- 1 second of this frame's absolute time
        active_items = []
        for item in scene.visual.ocr_text:
            item_time = getattr(item, 'time_sec', scene.start)
            if abs(sec_abs - item_time) <= 1.0:
                active_items.append(item)
            
        if active_items:
            # Create inpaint mask using exact polygons
            mask = np.zeros((height, width), dtype=np.uint8)
            for item in active_items:
                if not item.bbox:
                    continue
                poly = np.array(item.bbox, dtype=np.int32)
                poly = poly.reshape((-1, 1, 2))
                
                # Draw the exact slanted polygon, not a straight rectangle
                cv2.fillPoly(mask, [poly], 255)

            # Apply a 9x9 dilation (adds a motion buffer for 30-FPS video / 1-FPS OCR)
            # This prevents the text outline from remaining visible as a "ghost" after removal
            kernel = np.ones((9, 9), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)
            
            # High-speed CV2 Telea Inpainting
            frame = cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)
            
        writer.write(frame)
        frame_idx += 1
        
    cap.release()
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
