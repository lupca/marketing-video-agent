"""
Shared worker infrastructure for Celery-based video processing workers.
Extracts common patterns: Celery app factory, DB helpers, temp dir management.
"""

import os
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any

from celery import Celery

from shared_core.config import get_settings
from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog
from shared_core.minio_utils import ensure_bucket_exists, upload_file_to_minio

logger = logging.getLogger(__name__)


# ── Celery App Factory ────────────────────────────────────────────────────────

def create_celery_app(name: str) -> Celery:
    """Create a Celery app with standard configuration."""
    cfg = get_settings()
    app = Celery(name, broker=cfg.redis.url, backend=cfg.redis.url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Ho_Chi_Minh",
        enable_utc=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
    )
    return app


# ── DB Helpers ────────────────────────────────────────────────────────────────

def update_job(db, job: VideoJob, **kwargs) -> None:
    """Update job fields and commit."""
    for key, value in kwargs.items():
        setattr(job, key, value)
    db.commit()


def insert_log(db, job_id: int, message: str, level: str = "INFO") -> None:
    """Insert a log entry for a job."""
    log_level = logging.INFO if level == "INFO" else logging.ERROR
    logger.log(log_level, "[Job %d] %s", job_id, message)
    db.add(JobLog(job_id=job_id, log_level=level, message=message))
    db.commit()


# ── Output Upload ─────────────────────────────────────────────────────────────

def upload_output_video(db, job_id: int, job_type: str, output_video_path: str) -> Dict[str, str]:
    """
    Upload rendered video (and companion files like .ass subtitles) to MinIO.
    Returns dict of uploaded URLs.
    """
    ensure_bucket_exists()
    results = {}

    # Upload main video
    video_obj = f"outputs/{job_type}_job_{job_id}.mp4"
    results["video_url"] = upload_file_to_minio(video_obj, output_video_path)
    insert_log(db, job_id, f"Uploaded video to MinIO: {video_obj}")

    # Upload companion .ass files if present
    output_dir = os.path.dirname(output_video_path)
    base_name = os.path.splitext(os.path.basename(output_video_path))[0]

    for suffix, key in [("", "subtitle_url"), ("_captions", "captions_url")]:
        ass_path = os.path.join(output_dir, f"{base_name}{suffix}.ass")
        if os.path.isfile(ass_path):
            ass_obj = f"outputs/{job_type}_job_{job_id}{suffix}.ass"
            results[key] = upload_file_to_minio(ass_obj, ass_path)
            insert_log(db, job_id, f"Uploaded subtitle to MinIO: {ass_obj}")

    return results


# ── Task Executor ─────────────────────────────────────────────────────────────

def execute_video_task(
    job_id: int,
    config_data: Dict[str, Any],
    job_type: str,
    prepare_fn,
    build_fn,
    change_cwd: bool = False,
):
    """
    Generic video task executor. Handles the full lifecycle:
    1. DB status update → PROCESSING
    2. Call prepare_fn(config_data, work_dir) → local_config
    3. Call build_fn(local_config, work_dir) → output_path
    4. Upload output to MinIO
    5. Mark SUCCESS or FAILED

    Args:
        job_id: The VideoJob.id
        config_data: Raw config dict from the queue
        job_type: "review" or "unbox"
        prepare_fn: Callable(config_data, work_dir) → modified config
        build_fn: Callable(local_config, work_dir) → output_video_path
        change_cwd: If True, os.chdir to work_dir before build (for review worker)
    """
    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.warning("Job %d not found in DB, skipping.", job_id)
        db.close()
        return

    now = datetime.now(timezone.utc)
    update_job(db, job, status="PROCESSING", started_at=now, progress_percent=5)
    insert_log(db, job_id, "Job picked up by worker. Initializing...")

    work_dir = tempfile.mkdtemp(prefix=f"{job_type}_job_{job_id}_")
    prev_cwd = os.getcwd()

    try:
        # Step 1: Prepare assets
        insert_log(db, job_id, f"Preparing working directory: {work_dir}")
        local_config = prepare_fn(config_data, work_dir)
        update_job(db, job, progress_percent=10)
        insert_log(db, job_id, "Assets downloaded. Starting video build...")

        # Step 2: Build video
        if change_cwd:
            os.chdir(work_dir)

        output_video_path = build_fn(local_config, work_dir)
        update_job(db, job, progress_percent=80)
        insert_log(db, job_id, "Video build completed.")

        # Step 3: Upload
        insert_log(db, job_id, "Uploading output to storage...")
        upload_results = upload_output_video(db, job_id, job_type, output_video_path)
        update_job(db, job, progress_percent=95)

        # Step 4: Mark SUCCESS
        update_job(
            db, job,
            status="SUCCESS",
            result_url=upload_results["video_url"],
            progress_percent=100,
            completed_at=datetime.now(timezone.utc),
        )
        insert_log(db, job_id, "Job finished successfully.")

    except Exception as e:
        insert_log(db, job_id, f"Fatal error: {e}", "ERROR")
        update_job(
            db, job,
            status="FAILED",
            error_message=str(e)[:500],
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        if change_cwd:
            os.chdir(prev_cwd)
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
