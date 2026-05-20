import os
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

def separate_vocals_bgm(audio_path: str, work_dir: str) -> tuple[str, str]:
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

def transcribe_whisper(audio_path: str) -> list[dict]:
    """
    Transcribe vocal track using faster-whisper.
    Large-v3 model with INT8 quantization, using GPU.
    Runs fast and requires ~3GB VRAM.
    """
    logger.info("Loading faster-whisper (large-v3, INT8, GPU)...")
    try:
        from faster_whisper import WhisperModel
        
        # Init model on CUDA with INT8
        model = WhisperModel(
            "small",
            device="cuda",
            compute_type="int8",
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

def run_paddle_ocr(video_path: str, work_dir: str) -> list[dict]:
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
    
    # Capture one frame per second
    ocr_frames = []
    for sec in range(int(duration) + 1):
        frame_idx = int(sec * fps)
        if frame_idx >= frame_count:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_path = os.path.join(work_dir, f"ocr_frame_{sec:03d}.jpg")
        cv2.imwrite(frame_path, frame)
        ocr_frames.append((sec, frame_path))
        
    cap.release()
    
    if not ocr_frames:
        return []
        
    logger.info("Loading PaddleOCR (CPU, ultra-tight box params)...")
    try:
        from paddleocr import PaddleOCR
        
        # 1. TUNED PARAMETERS FOR TIGHT BOUNDING BOXES
        ocr = PaddleOCR(
            use_angle_cls=True, 
            lang="ch", 
            device="cpu", 
            enable_mkldnn=False, 
            ocr_version="PP-OCRv4",
            det_db_unclip_ratio=1.15,  # Forces bounding box to hug the text tightly
            det_db_thresh=0.35,        # Ignores faded edges
            det_db_box_thresh=0.6      # Drops low-confidence noise boxes
        )
        
        ocr_results = []
        for sec, frame_path in ocr_frames:
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
                        "time_sec": sec,
                        "bbox": bbox_polygon, 
                        "text": text.strip(),
                        "confidence": conf
                    })
            except Exception as frame_err:
                logger.warning(f"PaddleOCR skipped frame {sec} due to error: {frame_err}")
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
