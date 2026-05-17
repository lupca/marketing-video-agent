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
