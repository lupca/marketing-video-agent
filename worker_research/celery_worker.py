"""
Celery worker for Research jobs.
Exposes YouTube search and Video analysis tasks as background jobs if needed.
The Agent can either use these tasks async, or import the modules directly.
"""

from typing import List, Dict, Any, Optional
import os
import shutil
import tempfile
import logging

from shared_core.worker_base import create_celery_app
from shared_core.minio_utils import download_file_from_minio, get_object_name

from youtube_searcher import search_youtube_shorts, search_youtube_audio
from video_analyzer import analyze_video

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_research")

@celery_app.task(name="worker_research.tasks.search_videos")
def search_videos(keyword: str, count: int = 10, exclude_ids: Optional[List[str]] = None):
    """Celery task to search YouTube shorts."""
    return search_youtube_shorts(keyword, count, exclude_ids)

@celery_app.task(name="worker_research.tasks.search_audio")
def search_audio(keyword: str, count: int = 5):
    """Celery task to search YouTube audio."""
    return search_youtube_audio(keyword, count)

@celery_app.task(name="worker_research.tasks.analyze_video_from_storage")
def analyze_video_from_storage(s3_url: str):
    """Celery task to download an S3 video, analyze it, and return metadata."""
    if not s3_url.startswith("s3://"):
        return {"error": "Invalid S3 URL"}
        
    obj_name = get_object_name(s3_url)
    work_dir = tempfile.mkdtemp(prefix="research_")
    
    # Keep the same extension
    ext = os.path.splitext(obj_name)[1]
    if not ext: ext = ".mp4"
    
    local_path = os.path.join(work_dir, f"video{ext}")
    
    try:
        download_file_from_minio(obj_name, local_path)
        logger.info(f"Downloaded video for analysis: {local_path}")
        
        analysis = analyze_video(local_path)
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to analyze video: {e}")
        return {"error": str(e)}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
