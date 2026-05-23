import os
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["FLAGS_fraction_of_gpu_memory_to_use"] = "0.05"

import gc
import logging
import subprocess
import shutil
import json
from pathlib import Path

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

def extract_audio_gpu(video_path: str, work_dir: str) -> str:
    """
    Extract audio track from video using FFmpeg NVDEC.
    Output: vocal.wav / temporary audio file.
    """
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise FileNotFoundError("FFmpeg not found in path")
        
    out_audio = os.path.join(work_dir, "extracted_audio.wav")
    
    # Run FFmpeg to demux fast
    cmd = [
        ffmpeg_bin, "-y",
        "-hwaccel", "cuda",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",  # Whisper standard sample rate
        "-ac", "1",      # Mono audio
        out_audio
    ]
    
    logger.info("Extracting audio using FFmpeg NVDEC...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"FFmpeg audio extraction failed: {proc.stderr}")
        # Fallback to standard decode
        cmd_fallback = [ffmpeg_bin, "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", out_audio]
        subprocess.run(cmd_fallback, check=True)
        
    return out_audio

def _separate_vocals_bgm_inprocess(audio_path: str, work_dir: str) -> tuple[str, str]:
    """
    Use audio-separator to cleanly separate vocal and instrumental tracks.
    Uses MDX-Net ONNX model (approx 1.5GB VRAM).
    """
    logger.info("Starting Audio-Separator vocal separation...")
    try:
        from audio_separator.separator import Separator
        
        # Initialize separator with MDX model and GPU enabled
        separator = Separator(
            model_file_dir="/root/marketing-video-agent/worker_translify/model",
            output_dir=work_dir,
            output_format="wav",
            log_level=logging.WARNING
        )
        
        # Load the highly recommended fast MDX-Net model
        # UVR-MDX-NET-Inst_HQ_3 is exceptional for instrumental / vocals split
        separator.load_model("UVR-MDX-NET-Inst_HQ_3.onnx")
        
        logger.info("Splitting audio with MDX-Net ONNX model...")
        output_files = separator.separate(audio_path)
        
        vocal_file = ""
        bgm_file = ""
        
        for file in output_files:
            resolved_path = file if os.path.isabs(file) else os.path.join(work_dir, file)
            if "Vocals" in file:
                vocal_file = resolved_path
            elif "Instrumental" in file:
                bgm_file = resolved_path
                
        # If files are empty or not found, fallback to original as vocals and blank as bgm
        if not vocal_file or not os.path.exists(vocal_file):
            vocal_file = audio_path
        if not bgm_file or not os.path.exists(bgm_file):
            # Create a silent dummy BGM file
            bgm_file = os.path.join(work_dir, "dummy_bgm.wav")
            subprocess.run([
                shutil.which("ffmpeg"), "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                "-t", "5", bgm_file
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        logger.info(f"Separation complete. Vocals: {vocal_file}, BGM: {bgm_file}")
        
        # Free memory immediately
        del separator
        clean_gpu_memory()
        
        return vocal_file, bgm_file
    except Exception as e:
        logger.warning(f"Audio separator failed: {e}. Falling back to default split...")
        # Fallback: simple copy
        clean_gpu_memory()
        return audio_path, audio_path

def separate_vocals_bgm(audio_path: str, work_dir: str) -> tuple[str, str]:
    """Runs separate_vocals_bgm in an isolated subprocess to prevent CPU RAM accumulation."""
    import sys
    
    logger.info("Spawning isolated subprocess for separate_vocals_bgm...")
    out_json = os.path.join(work_dir, "separate_vocals_out.json")
    if os.path.exists(out_json):
        try: os.remove(out_json)
        except: pass
        
    cmd = [
        sys.executable,
        "-m", "translify_engine.cli_separate_vocals",
        "--audio-path", audio_path,
        "--work-dir", work_dir,
        "--output-json", out_json
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"Subprocess separate_vocals_bgm failed with code {proc.returncode}")
        logger.error(f"Subprocess stderr: {proc.stderr}")
        logger.error(f"Subprocess stdout: {proc.stdout}")
        # Fallback to in-process
        return _separate_vocals_bgm_inprocess(audio_path, work_dir)
        
    if not os.path.exists(out_json):
        logger.error("Subprocess completed but output JSON was not found. Falling back...")
        return _separate_vocals_bgm_inprocess(audio_path, work_dir)
        
    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    try: os.remove(out_json)
    except: pass
    
    return data["vocal"], data["bgm"]

def _transcribe_whisper_inprocess(audio_path: str) -> list[dict]:
    """
    Transcribe vocal track using faster-whisper.
    Large-v3 model with INT8 quantization, using GPU.
    Runs fast and requires ~3GB VRAM.
    """
    logger.info("Loading faster-whisper on CPU...")
    try:
        from faster_whisper import WhisperModel
        
        device = "cpu"
        compute_type = "float32"
        logger.info(f"Init WhisperModel on device={device} with compute_type={compute_type}")
        
        # Init model on CPU
        model = WhisperModel(
            "small",
            device=device,
            compute_type=compute_type,
            download_root=os.getenv("XDG_CACHE_HOME", "/root/.cache") + "/whisper"
        )
        
        logger.info("Transcribing audio with Whisper small...")
        # Douyin videos are Chinese (zh)
        segments, info = model.transcribe(
            audio_path,
            language="zh",
            beam_size=5,
            word_timestamps=False
        )
        
        results = []
        for segment in segments:
            results.append({
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "text": segment.text.strip(),
                "style": "Default"
            })
            
        logger.info(f"Transcription complete: {len(results)} segments found.")
        
        # Unload model
        del model
        clean_gpu_memory()
        return results
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        clean_gpu_memory()
        # Fallback empty segment list
        return []

def transcribe_whisper(audio_path: str) -> list[dict]:
    """Runs transcribe_whisper in an isolated subprocess to prevent CPU RAM accumulation."""
    import sys
    
    logger.info("Spawning isolated subprocess for transcribe_whisper...")
    out_json = os.path.join(os.path.dirname(audio_path), "transcribe_whisper_out.json")
    if os.path.exists(out_json):
        try: os.remove(out_json)
        except: pass
        
    cmd = [
        sys.executable,
        "-m", "translify_engine.cli_transcribe_whisper",
        "--audio-path", audio_path,
        "--output-json", out_json
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"Subprocess transcribe_whisper failed with code {proc.returncode}")
        logger.error(f"Subprocess stderr: {proc.stderr}")
        logger.error(f"Subprocess stdout: {proc.stdout}")
        return _transcribe_whisper_inprocess(audio_path)
        
    if not os.path.exists(out_json):
        logger.error("Subprocess completed but output JSON was not found. Falling back...")
        return _transcribe_whisper_inprocess(audio_path)
        
    with open(out_json, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    try: os.remove(out_json)
    except: pass
    
    return results

def _run_paddle_ocr_inprocess(video_path: str, work_dir: str) -> list[dict]:
    """
    Extract frames at 1fps and detect hardcoded Chinese text on screen using PaddleOCR.
    Output bounding boxes and texts so we can erase and translate them in Phase 3.
    PaddleOCR consumes ~1.5GB VRAM.
    """
    logger.info("Extracting frames for OCR analysis...")
    import cv2
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps
    
    # Capture 5 frames per second
    ocr_fps = 5.0
    ocr_frames = []
    total_samples = int(duration * ocr_fps) + 1
    for i in range(total_samples):
        t_sec = i / ocr_fps
        frame_idx = int(t_sec * fps)
        if frame_idx >= frame_count:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_path = os.path.join(work_dir, f"ocr_frame_{i:04d}.jpg")
        cv2.imwrite(frame_path, frame)
        ocr_frames.append((t_sec, frame_path))
        
    cap.release()
    
    if not ocr_frames:
        return []
        
    logger.info("Loading PaddleOCR...")
    try:
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
        logger.info(f"Loading PaddleOCR with use_gpu={use_gpu} on device={device} (ultra-tight box params)...")
        
        # 1. TUNED PARAMETERS FOR TIGHT BOUNDING BOXES
        ocr = PaddleOCR(
            use_angle_cls=True, 
            lang="ch", 
            use_gpu=use_gpu,
            device="gpu" if use_gpu else "cpu", 
            enable_mkldnn=False if use_gpu else True, 
            ocr_version="PP-OCRv4",
            det_db_unclip_ratio=1.15,  # Forces bounding box to hug the text tightly
            det_db_thresh=0.35,        # Ignores faded edges
            det_db_box_thresh=0.6,     # Drops low-confidence noise boxes
            ir_optim=False
        )
        
        # Dry run to verify GPU/cuDNN compatibility
        if use_gpu:
            try:
                import numpy as np
                dummy_img = np.zeros((32, 32, 3), dtype=np.uint8)
                ocr.ocr(dummy_img, cls=False)
                logger.info("PaddleOCR GPU dry run successful!")
            except Exception as dry_err:
                logger.warning(f"PaddleOCR GPU dry run failed (likely missing cuDNN or dynamic libraries): {dry_err}. Falling back to CPU...")
                use_gpu = False
                ocr = PaddleOCR(
                    use_angle_cls=True, 
                    lang="ch", 
                    use_gpu=False,
                    device="cpu", 
                    enable_mkldnn=True, 
                    ocr_version="PP-OCRv4",
                    det_db_unclip_ratio=1.15,
                    det_db_thresh=0.35,
                    det_db_box_thresh=0.6,
                    ir_optim=False
                )
        
        ocr_results = []
        for t_sec, frame_path in ocr_frames:
            try:
                result = ocr.ocr(frame_path)
                if not result or not result[0]:
                    continue
                    
                res_obj = result[0]
                # Check for newer PaddleOCR 3.x / PaddleX format (where res_obj is a dict/OCRResult)
                iterable_res = []
                if isinstance(res_obj, dict) or (hasattr(res_obj, "get") and "rec_texts" in res_obj):
                    texts = res_obj.get("rec_texts", [])
                    scores = res_obj.get("rec_scores", [])
                    polys = res_obj.get("dt_polys", [])
                    for t, s, p in zip(texts, scores, polys):
                        iterable_res.append((p, (t, s)))
                else:
                    iterable_res = res_obj
 
                for line in iterable_res:
                    # Defensive check on line structure returned by PaddleOCR
                    if not line or len(line) < 2 or not line[1] or len(line[1]) < 2:
                        continue
                        
                    poly = line[0]  # Array of 4 points: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    text = line[1][0]
                    conf = float(line[1][1])
                    
                    if conf <= 0.7:
                        continue
                        
                    # 2. PRESERVE THE EXACT POLYGON
                    bbox_polygon = [[float(p[0]), float(p[1])] for p in poly] if poly is not None else []
                    
                    ocr_results.append({
                        "time_sec": t_sec,
                        "bbox": bbox_polygon, 
                        "text": text.strip(),
                        "confidence": conf
                    })
            except Exception as frame_err:
                logger.warning(f"PaddleOCR skipped frame {t_sec:.2f} due to error: {frame_err}")
                continue
                
        logger.info(f"PaddleOCR scan complete. Found {len(ocr_results)} on-screen text elements.")
        
        # Cleanup PaddleOCR GPU memory
        del ocr
        clean_gpu_memory()
        return ocr_results
    except Exception as e:
        logger.error(f"PaddleOCR initialization failed: {e}")
        clean_gpu_memory()
        return []

def run_paddle_ocr(video_path: str, work_dir: str) -> list[dict]:
    """Runs run_paddle_ocr in an isolated subprocess to prevent CPU RAM accumulation."""
    import sys
    
    logger.info("Spawning isolated subprocess for run_paddle_ocr...")
    out_json = os.path.join(work_dir, "paddle_ocr_out.json")
    if os.path.exists(out_json):
        try: os.remove(out_json)
        except: pass
        
    cmd = [
        sys.executable,
        "-m", "translify_engine.cli_paddle_ocr",
        "--video-path", video_path,
        "--work-dir", work_dir,
        "--output-json", out_json
    ]
    
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"Subprocess run_paddle_ocr failed with code {proc.returncode}")
        logger.error(f"Subprocess stderr: {proc.stderr}")
        logger.error(f"Subprocess stdout: {proc.stdout}")
        return _run_paddle_ocr_inprocess(video_path, work_dir)
        
    if not os.path.exists(out_json):
        logger.error("Subprocess completed but output JSON was not found. Falling back...")
        return _run_paddle_ocr_inprocess(video_path, work_dir)
        
    with open(out_json, "r", encoding="utf-8") as f:
        results = json.load(f)
        
    try: os.remove(out_json)
    except: pass
    
    return results
