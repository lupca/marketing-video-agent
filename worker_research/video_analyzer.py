"""
Video Analyzer using ffprobe and PySceneDetect.
Returns structured data about a video file to help the LLM agent choose a worker.
"""

import os
import subprocess
import json
import logging
from typing import Dict, Any

from scenedetect import detect, ContentDetector

logger = logging.getLogger(__name__)

def analyze_video(video_path: str) -> Dict[str, Any]:
    """
    Analyzes a video locally and returns structured data.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
        
    tech_info = _get_ffprobe_info(video_path)
    
    # Run scene detection
    try:
        scene_list = detect(video_path, ContentDetector())
        scene_count = len(scene_list)
        
        duration = tech_info.get("duration", 0)
        avg_scene_duration = duration / scene_count if scene_count > 0 else duration
        
    except Exception as e:
        logger.error(f"Scene detection failed: {e}")
        scene_count = 1
        avg_scene_duration = tech_info.get("duration", 0)

    # Determine resolution and orientation
    width = tech_info.get("width", 1920)
    height = tech_info.get("height", 1080)
    is_vertical = height > width
    
    # Motion/Pacing heuristics
    motion_level = "low"
    if avg_scene_duration < 3.0:
        motion_level = "high"
    elif avg_scene_duration < 6.0:
        motion_level = "medium"

    # Return structured profile
    analysis = {
        "resolution": f"{width}x{height}",
        "duration_seconds": tech_info.get("duration", 0),
        "fps": tech_info.get("fps", 30),
        "has_audio": tech_info.get("has_audio", False),
        "scene_count": scene_count,
        "avg_scene_duration": round(avg_scene_duration, 2),
        "is_vertical": is_vertical,
        "motion_level": motion_level,
        "content_type_hints": {
            "promotion": round(_score_promotion(is_vertical, motion_level, scene_count), 2),
            "slideshow": round(_score_slideshow(is_vertical, motion_level, scene_count), 2),
            "review": round(_score_review(is_vertical, motion_level, scene_count), 2),
            "unbox_viral": round(_score_unbox(is_vertical, motion_level, scene_count), 2)
        }
    }
    
    return analysis

def _get_ffprobe_info(video_path: str) -> Dict[str, Any]:
    """Extract technical info using ffprobe."""
    cmd = [
        "ffprobe", 
        "-v", "quiet", 
        "-print_format", "json", 
        "-show_format", "-show_streams", 
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    info = {
        "width": 1920,
        "height": 1080,
        "duration": 0,
        "fps": 30,
        "has_audio": False
    }
    
    if result.returncode != 0:
        logger.warning(f"ffprobe failed: {result.stderr}")
        return info
        
    try:
        data = json.loads(result.stdout)
        
        if "format" in data and "duration" in data["format"]:
            info["duration"] = float(data["format"]["duration"])
            
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["width"] = int(stream.get("width", 1920))
                info["height"] = int(stream.get("height", 1080))
                # FPS is usually fractions like 30000/1001
                r_frame_rate = stream.get("r_frame_rate", "30/1")
                try:
                    num, den = map(int, r_frame_rate.split('/'))
                    info["fps"] = round(num / den, 2) if den > 0 else 30
                except:
                    pass
            elif stream.get("codec_type") == "audio":
                info["has_audio"] = True
                
    except Exception as e:
        logger.error(f"Failed to parse ffprobe output: {e}")
        
    return info

# Pre-defined simple heuristic scoring
def _score_promotion(is_vertical: bool, motion_level: str, scene_count: int) -> float:
    score = 0.5
    if is_vertical: score += 0.2
    if motion_level in ["high", "medium"]: score += 0.2
    return score

def _score_slideshow(is_vertical: bool, motion_level: str, scene_count: int) -> float:
    score = 0.5
    if is_vertical: score += 0.3
    if motion_level == "low" or scene_count <= 3: score += 0.3
    return score

def _score_review(is_vertical: bool, motion_level: str, scene_count: int) -> float:
    score = 0.5
    if not is_vertical: score += 0.2
    if motion_level == "medium" and scene_count > 2: score += 0.2
    return score

def _score_unbox(is_vertical: bool, motion_level: str, scene_count: int) -> float:
    score = 0.5
    if is_vertical: score += 0.2
    if motion_level == "high" and scene_count > 5: score += 0.3
    return score
