import os
import json
import tempfile
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from celery import Celery
from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog
from shared_core.minio_utils import (
    download_file_from_minio, upload_file_to_minio,
    is_minio_path, get_object_name, ensure_bucket_exists,
    minio_client, MINIO_BUCKET_NAME
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


# ─── Helper: Download a single s3:// path to a local path ────────────────────

def _download_s3(s3_url: str, local_path: str) -> str:
    """Download an s3:// URL to a local file path, creating dirs as needed."""
    obj_name = get_object_name(s3_url)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    download_file_from_minio(obj_name, local_path)
    logger.info(f"  ↓ Downloaded {obj_name} → {local_path}")
    return local_path


def _download_s3_folder(s3_prefix: str, local_dir: str):
    """
    Download all objects under an s3 prefix to a local directory.
    Used for segment clip folders like assets/segments/01_hook/
    """
    obj_name_prefix = get_object_name(s3_prefix.rstrip("/") + "/")
    os.makedirs(local_dir, exist_ok=True)

    objects = minio_client.list_objects(MINIO_BUCKET_NAME, prefix=obj_name_prefix, recursive=True)
    count = 0
    for obj in objects:
        filename = os.path.basename(obj.object_name)
        if not filename:
            continue
        local_path = os.path.join(local_dir, filename)
        download_file_from_minio(obj.object_name, local_path)
        count += 1
        logger.info(f"  ↓ Downloaded {obj.object_name} → {local_path}")

    if count == 0:
        logger.warning(f"  ⚠ No files found under prefix: {obj_name_prefix}")
    return count


# ─── Main: Prepare working directory from config_data ────────────────────────

def prepare_working_directory(config_data: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """
    Download all s3:// assets referenced in config_data to work_dir,
    recreating the directory structure that video_builder expects.

    Returns the modified config_data with local paths.

    Expected structure after download:
        work_dir/
        ├── raw/
        │   ├── voice.mp3          (voiceover)
        │   ├── voice.txt          (script)
        │   ├── bgm.mp3            (background music)
        │   ├── 1/                 (segment 01_hook clips)
        │   │   └── clip1.mov
        │   ├── 2/                 (segment 02_pain_point clips)
        │   │   └── clip2.mov
        │   └── ...
    """
    raw_dir = os.path.join(work_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # Deep copy to avoid mutating the original
    config = json.loads(json.dumps(config_data))

    assets = config.get("assets", {})
    audio = assets.get("audio", {})

    # ── 1. Download audio files ───────────────────────────────────────────
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

    # ── 2. Download video segment folders ─────────────────────────────────
    video_folders = assets.get("video_folders", {})
    new_video_folders = {}

    for idx, (folder_key, folder_path) in enumerate(video_folders.items(), start=1):
        local_segment_dir = os.path.join(raw_dir, str(idx))

        if is_minio_path(folder_path):
            # s3://videos/assets/segments/01_hook/ → download all clips
            _download_s3_folder(folder_path, local_segment_dir)
        else:
            # Local path (backwards compat) — just ensure it's valid
            local_segment_dir = folder_path

        new_video_folders[folder_key] = f"raw/{idx}/"

    assets["video_folders"] = new_video_folders

    return config


# ─── DB update helper ────────────────────────────────────────────────────────

def _insert_log(db, job_id, message, level="INFO"):
    """Helper to insert a log line to JobLog."""
    logger.log(logging.INFO if level == "INFO" else logging.ERROR, f"[Job {job_id}] {message}")
    db.add(JobLog(job_id=job_id, log_level=level, message=message))
    db.commit()

def _update_job(db, job, **kwargs):
    """Helper to update job fields and commit."""
    for k, v in kwargs.items():
        setattr(job, k, v)
    db.commit()


# ─── Upload output files ─────────────────────────────────────────────────────

def _upload_output_files(db, job_id: int, output_video_path: str):
    """Upload the rendered video (and related files) to MinIO and return s3 URLs."""
    ensure_bucket_exists()
    results = {}

    # Upload video
    video_obj = f"outputs/review_job_{job_id}.mp4"
    results["video_url"] = upload_file_to_minio(video_obj, output_video_path)
    _insert_log(db, job_id, f"Uploaded video output to MinIO: {video_obj}")

    # Upload ASS subtitle if exists (same directory)
    output_dir = os.path.dirname(output_video_path)
    base_name = os.path.splitext(os.path.basename(output_video_path))[0]

    ass_path = os.path.join(output_dir, f"{base_name}.ass")
    if os.path.isfile(ass_path):
        ass_obj = f"outputs/review_job_{job_id}.ass"
        results["subtitle_url"] = upload_file_to_minio(ass_obj, ass_path)
        _insert_log(db, job_id, f"Uploaded subtitle script to MinIO: {ass_obj}")

    captions_ass = os.path.join(output_dir, f"{base_name}_captions.ass")
    if os.path.isfile(captions_ass):
        cap_obj = f"outputs/review_job_{job_id}_captions.ass"
        results["captions_url"] = upload_file_to_minio(cap_obj, captions_ass)
        _insert_log(db, job_id, f"Uploaded captions effect to MinIO: {cap_obj}")

    return results


# ─── Celery Task ──────────────────────────────────────────────────────────────

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
    _insert_log(db, job_id, "Job mapped to Worker. Initializing process in pending queue.")

    work_dir = tempfile.mkdtemp(prefix=f"job_{job_id}_")
    prev_cwd = os.getcwd()

    try:
        # Step 1: Download assets from MinIO and rebuild directory structure
        _insert_log(db, job_id, f"Preparing working directory in {work_dir}. Linking remote S3 assets...")
        local_config = prepare_working_directory(config_data, work_dir)
        _update_job(db, job, progress_percent=10)
        _insert_log(db, job_id, "Remote assets downloaded. Proceeding to assemble sequence.")

        # Step 2: Change to work_dir so VideoBuilder resolves paths correctly
        os.chdir(work_dir)
        _insert_log(db, job_id, "Triggering video_builder build pipeline. This might take several minutes...", "INFO")
        output_video_path = build_video(local_config, preview=False)
        _update_job(db, job, progress_percent=80)
        _insert_log(db, job_id, "Video assembly and FFmpeg render completed gracefully. Output constructed.")

        # Step 3: Upload output to MinIO
        _insert_log(db, job_id, "Uploading output results to Video Creator Storage...")
        upload_results = _upload_output_files(db, job_id, output_video_path)
        _update_job(db, job, progress_percent=95)

        # Step 4: Mark SUCCESS
        _update_job(db, job,
                    status="SUCCESS",
                    result_url=upload_results["video_url"],
                    progress_percent=100,
                    completed_at=datetime.now(timezone.utc))

        _insert_log(db, job_id, "Job finished successfully. Output ready for user.", "INFO")

    except Exception as e:
        _insert_log(db, job_id, f"Fatal error executing pipeline: {e}", "ERROR")
        _update_job(db, job,
                    status="FAILED",
                    error_message=str(e)[:500],
                    completed_at=datetime.now(timezone.utc))
    finally:
        os.chdir(prev_cwd)
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
