"""
Celery worker for Video Review jobs.
Uses shared worker_base for common infrastructure.
Algorithm logic (video_builder.build_video) is untouched.
"""

import os
import json
import logging
from typing import Dict, Any

from shared_core.worker_base import create_celery_app, execute_video_task
from shared_core.minio_utils import (
    download_file_from_minio, is_minio_path, get_object_name,
    get_minio_client, get_bucket_name,
)
from shared_core.gpu_utils import ensure_h264_mp4

from video_builder import build_video

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_review", worker_type="review")


# ── Asset Download Helpers (review-specific) ─────────────────────────────────

def _download_s3(s3_url: str, local_path: str) -> str:
    """Download an s3:// URL to a local file path."""
    obj_name = get_object_name(s3_url)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    download_file_from_minio(obj_name, local_path)
    
    # Normalize if it's a video file to prevent AV1/VP9 OpenCV decoding issues
    ext = os.path.splitext(local_path)[1].lower()
    if ext in (".mp4", ".webm", ".mov", ".mkv"):
        local_path = ensure_h264_mp4(local_path)
        
    logger.info("  ↓ Downloaded %s → %s", obj_name, local_path)
    return local_path


def _download_s3_folder(s3_prefix: str, local_dir: str) -> int:
    """Download all objects under an s3 prefix to a local directory."""
    obj_name_prefix = get_object_name(s3_prefix.rstrip("/") + "/")
    os.makedirs(local_dir, exist_ok=True)

    client = get_minio_client()
    bucket = get_bucket_name()
    objects = client.list_objects(bucket, prefix=obj_name_prefix, recursive=True)
    count = 0
    for obj in objects:
        filename = os.path.basename(obj.object_name)
        if not filename:
            continue
        local_path = os.path.join(local_dir, filename)
        download_file_from_minio(obj.object_name, local_path)
        
        # Normalize if it's a video file to prevent AV1/VP9 OpenCV decoding issues
        ext = os.path.splitext(local_path)[1].lower()
        if ext in (".mp4", ".webm", ".mov", ".mkv"):
            local_path = ensure_h264_mp4(local_path)
            
        count += 1
        logger.info("  ↓ Downloaded %s → %s", obj.object_name, local_path)

    if count == 0:
        logger.warning("  ⚠ No files found under prefix: %s", obj_name_prefix)
    return count


# ── Prepare Working Directory ────────────────────────────────────────────────

def prepare_working_directory(config_data: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """
    Download all s3:// assets referenced in config_data to work_dir,
    recreating the directory structure that video_builder expects.

    Expected structure after download:
        work_dir/
        ├── raw/
        │   ├── voice.mp3
        │   ├── voice.txt
        │   ├── bgm.mp3
        │   ├── 1/   (segment clips)
        │   ├── 2/
        │   └── ...
    """
    raw_dir = os.path.join(work_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # Deep copy to avoid mutating the original
    config = json.loads(json.dumps(config_data))

    assets = config.get("assets", {})
    audio = assets.get("audio", {})

    # 1. Download audio files
    if audio.get("voiceover_path") and is_minio_path(audio["voiceover_path"]):
        local = os.path.join(raw_dir, "voice.mp3")
        _download_s3(audio["voiceover_path"], local)
        audio["voiceover_path"] = "raw/voice.mp3"

    if audio.get("voiceover_script") and is_minio_path(audio["voiceover_script"]):
        local = os.path.join(raw_dir, "voice.txt")
        _download_s3(audio["voiceover_script"], local)
        audio["voiceover_script"] = "raw/voice.txt"

    if audio.get("bgm_path") and is_minio_path(audio["bgm_path"]):
        local = os.path.join(raw_dir, "bgm.mp3")
        _download_s3(audio["bgm_path"], local)
        audio["bgm_path"] = "raw/bgm.mp3"

    # 2. Download video segment folders
    video_folders = assets.get("video_folders", {})
    new_video_folders = {}

    for idx, (folder_key, folder_path) in enumerate(video_folders.items(), start=1):
        local_segment_dir = os.path.join(raw_dir, str(idx))

        if is_minio_path(folder_path):
            _download_s3_folder(folder_path, local_segment_dir)
        else:
            local_segment_dir = folder_path

        new_video_folders[folder_key] = f"raw/{idx}/"

    assets["video_folders"] = new_video_folders

    return config


# ── Build Function Adapter ───────────────────────────────────────────────────

def _build_review_video(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: call build_video with the right signature."""
    return build_video(local_config, preview=False)


# ── Celery Task ──────────────────────────────────────────────────────────────

@celery_app.task(name="worker_review.tasks.process_video", bind=True, max_retries=2)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="review",
        prepare_fn=prepare_working_directory,
        build_fn=_build_review_video,
        change_cwd=True,
    )
