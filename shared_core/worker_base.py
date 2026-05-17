"""
Shared worker infrastructure for Celery-based video processing workers.
Extracts common patterns: Celery app factory, DB helpers, temp dir management.
"""

import os
import logging
import shutil
import tempfile
import threading
import time
import uuid
import socket
from datetime import datetime, timezone
from typing import Dict, Any

from celery import Celery
from celery.signals import worker_ready, worker_shutting_down

from shared_core.config import get_settings
from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog, WorkerNode, WorkerConfig
from shared_core.minio_utils import ensure_bucket_exists, upload_file_to_minio

logger = logging.getLogger(__name__)


# ── Celery App Factory ────────────────────────────────────────────────────────

_worker_app_name = "Unknown Worker"
_worker_type = None    # Set by create_celery_app, used by heartbeat for self-termination

def is_worker_enabled(worker_type: str) -> bool:
    """
    Check if a specific worker type is enabled in the database.
    Default to True (fail-open) if database connection fails.
    """
    try:
        with SessionLocal() as db:
            config = db.query(WorkerConfig).filter(WorkerConfig.worker_type == worker_type).first()
            if config is None:
                # If not in DB, it's considered disabled until initialized
                return False
            return config.is_enabled
    except Exception as e:
        logger.error(f"Failed to check enablement for {worker_type}: {e}")
        return True # Fail-open: allow running if DB is down


def log_worker_startup_info(worker_type: str):
    """Log whether the worker is starting in enabled or disabled mode."""
    enabled = is_worker_enabled(worker_type)
    if enabled:
        logger.info(f"🚀 Worker '{worker_type}' is ENABLED. Processing tasks normally.")
    else:
        logger.warning(f"⚠️  Worker '{worker_type}' is DISABLED in config!")
        logger.warning("Worker will start but will NOT process any tasks if ENFORCE_WORKER_ENABLED=true.")


def create_celery_app(name: str, worker_type: str = None) -> Celery:
    """Create a Celery app with standard configuration."""
    global _worker_app_name, _worker_type
    _worker_app_name = name
    _worker_type = worker_type
    
    # ── NEW: Kiểm tra worker enablement ──
    if worker_type:
        is_enabled = is_worker_enabled(worker_type)
        log_worker_startup_info(worker_type)
        
        # Nếu ENFORCE_WORKER_ENABLED=true, dừng startup khi disabled
        enforce = os.getenv("ENFORCE_WORKER_ENABLED", "false").lower() == "true"
        if enforce and not is_enabled:
            logger.critical(f"❌ FATAL: Worker '{worker_type}' is disabled and ENFORCE_WORKER_ENABLED is set.")
            raise RuntimeError(
                f"❌ Worker '{worker_type}' is DISABLED and ENFORCE_WORKER_ENABLED=true. "
                f"Cannot start."
            )
    # ── END NEW ──
    
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


# ── Worker Heartbeat ──────────────────────────────────────────────────────────

WORKER_ID = str(uuid.uuid4())
HOSTNAME = socket.gethostname()
HEARTBEAT_INTERVAL = 10
_heartbeat_thread = None
_stop_heartbeat = threading.Event()
_current_job_id = None
_supported_types = []  # Optionally set by specific workers


def _heartbeat_loop():
    while not _stop_heartbeat.is_set():
        try:
            # Check if this worker has been disabled — if so, shut down gracefully
            if _worker_type:
                try:
                    with SessionLocal() as db:
                        config = db.query(WorkerConfig).filter(WorkerConfig.worker_type == _worker_type).first()
                        if config and not config.is_enabled:
                            logger.critical(f"🛑 Worker '{_worker_type}' has been DISABLED. Shutting down...")
                            import signal
                            os.kill(os.getpid(), signal.SIGTERM)
                            return
                except (ProcessLookupError, OSError):
                    return # Already dying
                except Exception as e:
                    logger.error(f"Error in heartbeat kill check: {e}")

            with SessionLocal() as db:
                worker = db.query(WorkerNode).filter(WorkerNode.id == WORKER_ID).first()
                now = datetime.now(timezone.utc)
                if not worker:
                    worker = WorkerNode(
                        id=WORKER_ID,
                        hostname=f"[{_worker_app_name}] {HOSTNAME}",
                        supported_types=_supported_types,
                        status="ONLINE",
                        current_job_id=_current_job_id,
                        last_heartbeat=now
                    )
                    db.add(worker)
                else:
                    worker.hostname = f"[{_worker_app_name}] {HOSTNAME}"
                    worker.status = "ONLINE"
                    worker.current_job_id = _current_job_id
                    worker.last_heartbeat = now
                    db.commit()
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
        
        # Sleep in short intervals to allow quick thread exit
        for _ in range(HEARTBEAT_INTERVAL):
            if _stop_heartbeat.is_set():
                break
            time.sleep(1)


@worker_ready.connect
def start_heartbeat(**kwargs):
    global _heartbeat_thread
    _heartbeat_thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    _heartbeat_thread.start()
    logger.info(f"Started worker heartbeat for node {WORKER_ID}")


@worker_shutting_down.connect
def stop_heartbeat(**kwargs):
    _stop_heartbeat.set()
    if _heartbeat_thread:
        _heartbeat_thread.join(timeout=2)
    
    # Attempt to mark offline
    try:
        db = SessionLocal()
        worker = db.query(WorkerNode).filter(WorkerNode.id == WORKER_ID).first()
        if worker:
            worker.status = "OFFLINE"
            worker.current_job_id = None
            worker.last_heartbeat = datetime.now(timezone.utc)
            db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Failed to set offline status for {WORKER_ID}: {e}")


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
    global _current_job_id

    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.warning("Job %d not found in DB, skipping.", job_id)
        db.close()
        return

    _current_job_id = job_id

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
        _current_job_id = None
        if change_cwd:
            os.chdir(prev_cwd)
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
