"""
Celery worker for Video Unbox jobs.
Uses shared worker_base for common infrastructure.
Algorithm logic (make_viral) is untouched.
"""

import os
import logging
from typing import Dict, Any

from shared_core.worker_base import create_celery_app, execute_video_task
from shared_core.minio_utils import (
    download_file_from_minio, is_minio_path, get_object_name,
    is_downloadable_path, download_file_or_s3
)
from shared_core.gpu_utils import ensure_h264_mp4

from make_viral import make_viral
from unbox_viral import make_unbox_viral

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_unbox", worker_type="unbox")


# ── Prepare Assets (unbox-specific) ──────────────────────────────────────────

def download_unbox_assets(config_data: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """Download MinIO assets specific to unbox worker."""
    input_dir = os.path.join(work_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    # Deep copy to avoid mutating original
    import json
    config = json.loads(json.dumps(config_data))

    # Support unified Scene-Centric Schema
    if "scenes" in config:
        # Download bgm
        bgm_url = config.get("bgm_path") or config.get("audio", "")
        if bgm_url and is_downloadable_path(bgm_url):
            filename = os.path.basename(bgm_url.split("?")[0]) or "bg_music.mp3"
            if not filename.lower().endswith(".mp3"):
                filename = "bg_music.mp3"
            local_path = os.path.join(input_dir, filename)
            download_file_or_s3(bgm_url, local_path)
            config["bgm_path"] = local_path
            if "audio" in config:
                config["audio"] = local_path

        # Download scenes video clips
        for idx, s in enumerate(config.get("scenes", [])):
            clip_url = s.get("clip_url", "")
            if clip_url and is_downloadable_path(clip_url):
                filename = os.path.basename(clip_url.split("?")[0]) or f"clip_{idx+1}.mp4"
                if not any(filename.lower().endswith(ext) for ext in [".mp4", ".mov", ".avi", ".webm", ".mkv"]):
                    filename = f"clip_{idx+1}.mp4"
                local_path = os.path.join(input_dir, filename)
                download_file_or_s3(clip_url, local_path)
                
                # Ensure standard H.264 MP4 format
                local_path = ensure_h264_mp4(local_path)
                s["clip_url"] = local_path

    # Support legacy schema
    else:
        for key in ("clips", "video"):
            if key in config:
                items = config[key]
                if isinstance(items, str):
                    items = [items]
                for i, clip_url in enumerate(items):
                    if is_minio_path(clip_url):
                        obj_name = get_object_name(clip_url)
                        local_path = os.path.join(input_dir, os.path.basename(obj_name))
                        download_file_from_minio(obj_name, local_path)
                        
                        # Ensure standard H.264 MP4 format
                        local_path = ensure_h264_mp4(local_path)
                        
                        if isinstance(config[key], list):
                            config[key][i] = local_path
                        else:
                            config[key] = local_path

        if "audio" in config:
            audio_url = config["audio"]
            if is_minio_path(audio_url):
                obj_name = get_object_name(audio_url)
                local_path = os.path.join(input_dir, os.path.basename(obj_name))
                download_file_from_minio(obj_name, local_path)
                config["audio"] = local_path

    return config


# ── Build Function Adapters ──────────────────────────────────────────────────

def _build_unbox_video(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: call make_viral with the right signature."""
    return make_viral(work_dir=work_dir, config=local_config, preview=False)


def _build_unbox_viral_video(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: call make_unbox_viral (smart crop + speed ramp pipeline)."""
    return make_unbox_viral(work_dir=work_dir, config=local_config)


# ── Celery Tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="worker_unbox.tasks.process_video", bind=True, max_retries=2)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="unbox",
        prepare_fn=download_unbox_assets,
        build_fn=_build_unbox_video,
        change_cwd=False,
    )


@celery_app.task(name="worker_unbox.tasks.process_unbox_viral", bind=True, max_retries=2)
def process_unbox_viral(self, job_id: int, config_data: Dict[str, Any]):
    """Process an unbox video with smart crop, speed ramping, and beat-sync."""
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="unbox_viral",
        prepare_fn=download_unbox_assets,
        build_fn=_build_unbox_viral_video,
        change_cwd=False,
    )

