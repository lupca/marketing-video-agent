import os
import json
import tempfile
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any

from celery import Celery
from shared_core.database import SessionLocal
from shared_core.models import VideoJob
from shared_core.minio_utils import (
    download_file_from_minio, upload_file_to_minio,
    is_minio_path, get_object_name, ensure_bucket_exists
)

from make_viral import make_viral

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker_unbox",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    worker_prefetch_multiplier=1,
)

def download_unbox_assets(config_data: Dict[str, Any], work_dir: str):
    """Download minio assets specific to unbox worker."""
    input_dir = os.path.join(work_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    if "clips" in config_data:
        for i, clip_url in enumerate(config_data["clips"]):
            if is_minio_path(clip_url):
                obj_name = get_object_name(clip_url)
                local_path = os.path.join(input_dir, os.path.basename(obj_name))
                download_file_from_minio(obj_name, local_path)
                config_data["clips"][i] = local_path

    if "audio" in config_data:
        audio_url = config_data["audio"]
        if is_minio_path(audio_url):
            obj_name = get_object_name(audio_url)
            local_path = os.path.join(input_dir, os.path.basename(obj_name))
            download_file_from_minio(obj_name, local_path)
            config_data["audio"] = local_path


def _update_job(db, job, **kwargs):
    """Helper to update job fields and commit."""
    for k, v in kwargs.items():
        setattr(job, k, v)
    db.commit()


def _upload_output_files(job_id: int, output_video_path: str):
    """Upload the rendered video to MinIO and return s3 URL."""
    ensure_bucket_exists()

    video_obj = f"outputs/unbox_job_{job_id}.mp4"
    video_url = upload_file_to_minio(video_obj, output_video_path)
    logger.info(f"  ✔ Uploaded video → {video_url}")
    return video_url


@celery_app.task(name="worker_unbox.tasks.process_video", bind=True)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        db.close()
        return

    now = datetime.now(timezone.utc)
    _update_job(db, job,
                status="PROCESSING",
                started_at=now,
                progress_percent=5)

    work_dir = tempfile.mkdtemp(prefix=f"unbox_job_{job_id}_")
    try:
        # Step 1: Download s3 inputs
        download_unbox_assets(config_data, work_dir)
        _update_job(db, job, progress_percent=10)

        # Step 2: Build video
        logger.info(f"[Job {job_id}] Starting unbox video build...")
        output_video_path = make_viral(work_dir=work_dir, config=config_data, preview=False)
        _update_job(db, job, progress_percent=80)

        # Step 3: Upload output to MinIO
        logger.info(f"[Job {job_id}] Uploading output to MinIO...")
        video_url = _upload_output_files(job_id, output_video_path)
        _update_job(db, job, progress_percent=95)

        # Step 4: Mark SUCCESS
        _update_job(db, job,
                    status="SUCCESS",
                    result_url=video_url,
                    progress_percent=100,
                    completed_at=datetime.now(timezone.utc))

        logger.info(f"[Job {job_id}] ✓ Complete → {video_url}")

    except Exception as e:
        logger.error(f"[Job {job_id}] ✗ Failed: {e}", exc_info=True)
        _update_job(db, job,
                    status="FAILED",
                    error_message=str(e)[:500],
                    completed_at=datetime.now(timezone.utc))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
