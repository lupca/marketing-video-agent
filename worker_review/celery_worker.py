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

from video_builder import build_video

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker_review",
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

def find_and_download_minio_assets(data: Any, work_dir: str):
    """Recursively search for s3:// URLs in config and download them to work_dir."""
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str) and is_minio_path(v):
                obj_name = get_object_name(v)
                local_path = os.path.join(work_dir, os.path.basename(obj_name))
                download_file_from_minio(obj_name, local_path)
                data[k] = local_path
            else:
                find_and_download_minio_assets(v, work_dir)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, str) and is_minio_path(item):
                obj_name = get_object_name(item)
                local_path = os.path.join(work_dir, os.path.basename(obj_name))
                download_file_from_minio(obj_name, local_path)
                data[i] = local_path
            else:
                find_and_download_minio_assets(item, work_dir)


def _update_job(db, job, **kwargs):
    """Helper to update job fields and commit."""
    for k, v in kwargs.items():
        setattr(job, k, v)
    db.commit()


def _upload_output_files(job_id: int, output_video_path: str):
    """Upload the rendered video (and related files) to MinIO and return s3 URLs."""
    ensure_bucket_exists()
    results = {}

    # Upload video
    video_obj = f"outputs/review_job_{job_id}.mp4"
    results["video_url"] = upload_file_to_minio(video_obj, output_video_path)
    logger.info(f"  ✔ Uploaded video → {results['video_url']}")

    # Upload ASS subtitle if exists (same directory)
    output_dir = os.path.dirname(output_video_path)
    base_name = os.path.splitext(os.path.basename(output_video_path))[0]

    ass_path = os.path.join(output_dir, f"{base_name}.ass")
    if os.path.isfile(ass_path):
        ass_obj = f"outputs/review_job_{job_id}.ass"
        results["subtitle_url"] = upload_file_to_minio(ass_obj, ass_path)
        logger.info(f"  ✔ Uploaded subtitle → {results['subtitle_url']}")

    captions_ass = os.path.join(output_dir, f"{base_name}_captions.ass")
    if os.path.isfile(captions_ass):
        cap_obj = f"outputs/review_job_{job_id}_captions.ass"
        results["captions_url"] = upload_file_to_minio(cap_obj, captions_ass)
        logger.info(f"  ✔ Uploaded captions → {results['captions_url']}")

    return results


@celery_app.task(name="worker_review.tasks.process_video", bind=True)
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

    work_dir = tempfile.mkdtemp(prefix=f"job_{job_id}_")
    try:
        # Step 1: Download any s3 inputs
        find_and_download_minio_assets(config_data, work_dir)
        _update_job(db, job, progress_percent=10)

        # Step 2: Build video
        logger.info(f"[Job {job_id}] Starting video build...")
        output_video_path = build_video(config_data, preview=False)
        _update_job(db, job, progress_percent=80)

        # Step 3: Upload output to MinIO
        logger.info(f"[Job {job_id}] Uploading output to MinIO...")
        upload_results = _upload_output_files(job_id, output_video_path)
        _update_job(db, job, progress_percent=95)

        # Step 4: Mark SUCCESS
        _update_job(db, job,
                    status="SUCCESS",
                    result_url=upload_results["video_url"],
                    progress_percent=100,
                    completed_at=datetime.now(timezone.utc))

        logger.info(f"[Job {job_id}] ✓ Complete → {upload_results['video_url']}")

    except Exception as e:
        logger.error(f"[Job {job_id}] ✗ Failed: {e}", exc_info=True)
        _update_job(db, job,
                    status="FAILED",
                    error_message=str(e)[:500],
                    completed_at=datetime.now(timezone.utc))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
