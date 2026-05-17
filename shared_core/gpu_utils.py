"""GPU and hardware encoder detection utilities.
Provides robust detection and configuration for hardware-accelerated video encoding.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def detect_ffmpeg_hw_encoder() -> str:
    """Detect the best available hardware H.264 video encoder on this system.
    
    Priority: h264_nvenc (NVIDIA) > h264_videotoolbox (macOS) > libx264 (CPU fallback)
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return "libx264"
    
    try:
        proc = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            if "h264_nvenc" in proc.stdout:
                logger.info("GPU hardware encoder detected: h264_nvenc")
                return "h264_nvenc"
            if "h264_videotoolbox" in proc.stdout:
                logger.info("GPU hardware encoder detected: h264_videotoolbox")
                return "h264_videotoolbox"
    except Exception as e:
        logger.warning(f"Failed to detect hardware encoder, using CPU fallback. Error: {e}")
        
    return "libx264"

def get_ffmpeg_encoder_args(crf: int = 20, preset: str = "veryfast") -> list[str]:
    """Get FFmpeg video encoder arguments based on the best detected encoder.
    
    Ensures safe encoding with optimized performance.
    """
    encoder = detect_ffmpeg_hw_encoder()
    
    if encoder == "h264_nvenc":
        # Balanced high-performance settings for NVIDIA NVENC
        return [
            "-c:v", "h264_nvenc",
            "-preset", "p4",        # balanced/medium speed preset for NVENC (good quality)
            "-rc", "vbr",           # variable bitrate
            "-cq", str(crf),        # constant quality target
            "-profile:v", "high",
        ]
    
    if encoder == "h264_videotoolbox":
        return [
            "-c:v", "h264_videotoolbox",
            "-q:v", "65",
            "-profile:v", "high",
            "-level", "4.1",
        ]
        
    # Standard high-compatibility CPU fallback
    return [
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
    ]

def detect_torch_device() -> str:
    """Detect the best PyTorch device: cuda > mps > cpu."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"

def check_video_codec(video_path: str) -> str | None:
    """Get the video stream codec name using ffprobe."""
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        logger.warning("ffprobe not found in PATH")
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception as e:
        logger.warning(f"Failed to check video codec with ffprobe: {e}")
    return None

def ensure_h264_mp4(video_path: str) -> str:
    """Check if the video is already H.264 MP4. If not, transcode it to H.264 MP4.
    Returns the path to the H.264 MP4 video file.
    """
    codec = check_video_codec(video_path)
    ext = os.path.splitext(video_path)[1].lower()
    
    # If already h264/avc1 and in mp4 format, return as is
    if codec in ("h264", "avc1") and ext == ".mp4":
        logger.info(f"Video {video_path} is already H.264 MP4.")
        return video_path
        
    logger.info(f"Video {video_path} is codec={codec}, ext={ext}. Transcoding to standard H.264 MP4...")
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        logger.warning("ffmpeg not found, cannot transcode video!")
        return video_path
        
    # Generate a temp output path in the same directory
    dir_name = os.path.dirname(video_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    temp_out_path = os.path.join(dir_name, f"{base_name}_normalized.mp4")
    
    # Use GPU NVENC if available, fallback to CPU libx264
    enc_args = get_ffmpeg_encoder_args(crf=20, preset="veryfast")
    
    cmd = [
        ffmpeg_path, "-y",
        "-i", str(video_path),
        *enc_args,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",           # transcode audio to standard AAC to ensure compatibility
        "-movflags", "+faststart",
        temp_out_path
    ]
    
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300, # 5 min timeout
        )
        if proc.returncode == 0:
            logger.info(f"Successfully transcoded {video_path} to H.264 MP4.")
            # Remove original and replace with normalized one
            try:
                if os.path.exists(video_path):
                    os.remove(video_path)
                os.rename(temp_out_path, video_path)
                # Ensure extension is .mp4
                if ext != ".mp4":
                    new_mp4_path = os.path.splitext(video_path)[0] + ".mp4"
                    os.rename(video_path, new_mp4_path)
                    return new_mp4_path
            except Exception as e:
                logger.warning(f"Failed to replace original file with transcoded file: {e}")
                return temp_out_path
            return video_path
        else:
            logger.error(f"Transcoding failed (exit {proc.returncode}): {proc.stderr}")
    except Exception as e:
        logger.error(f"Transcoding failed with exception: {e}")
        
    return video_path
