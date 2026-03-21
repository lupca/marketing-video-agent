"""
Celery worker for Video Download jobs.
Uses yt-dlp to download videos from URLs, uploads to MinIO, and creates Asset records.
"""

import os
import uuid
import glob
import logging
import subprocess
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any

from shared_core.worker_base import create_celery_app, update_job, insert_log
from shared_core.database import SessionLocal
from shared_core.models import VideoJob, Asset
from shared_core.minio_utils import ensure_bucket_exists, upload_file_to_minio

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_download")


def _run_ytdlp(url: str, output_dir: str) -> str:
    """
    Run yt-dlp to download a video.
    Returns the path to the downloaded file.
    """
    output_template = os.path.join(output_dir, "%(title).80s_%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--no-overwrites",
        "-o", output_template,
        url,
    ]
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,  # 10-minute timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed (exit {result.returncode}): {result.stderr[:500]}")

    # Find the downloaded mp4 file
    mp4_files = glob.glob(os.path.join(output_dir, "*.mp4"))
    if not mp4_files:
        # Fallback: look for any video file
        all_files = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
        if not all_files:
            raise RuntimeError(f"yt-dlp ran successfully but no files found in {output_dir}")
        return os.path.join(output_dir, all_files[0])
    return mp4_files[0]


@celery_app.task(name="worker_download.tasks.process_video", bind=True, max_retries=1)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    """
    Download a video from URL using yt-dlp, upload to MinIO, and create an Asset.
    
    config_data:
        url: str — URL to download
        user_id: str — owner user ID (injected by the API)
    """
    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.warning("Job %d not found in DB, skipping.", job_id)
        db.close()
        return

    url = config_data.get("url")
    user_id = config_data.get("user_id")

    if not url:
        update_job(db, job, status="FAILED", error_message="Missing 'url' in config_data")
        db.close()
        return

    now = datetime.now(timezone.utc)
    update_job(db, job, status="PROCESSING", started_at=now, progress_percent=5)
    insert_log(db, job_id, f"Starting download from: {url}")

    work_dir = tempfile.mkdtemp(prefix=f"download_job_{job_id}_")
    try:
        # Step 1: Download with yt-dlp
        insert_log(db, job_id, "Running yt-dlp...")
        update_job(db, job, progress_percent=10)
        downloaded_path = _run_ytdlp(url, work_dir)
        file_name = os.path.basename(downloaded_path)
        file_size = os.path.getsize(downloaded_path)
        insert_log(db, job_id, f"Downloaded: {file_name} ({file_size} bytes)")
        update_job(db, job, progress_percent=50)

        # Step 2: Upload to MinIO
        insert_log(db, job_id, "Uploading to MinIO...")
        ensure_bucket_exists()
        uid = str(uuid.uuid4())[:8]
        object_name = f"assets/video/{uid}_{file_name}"
        s3_url = upload_file_to_minio(object_name, downloaded_path)
        update_job(db, job, progress_percent=80)
        insert_log(db, job_id, f"Uploaded to MinIO: {object_name}")

        # Step 3: Create Asset record if user_id provided
        if user_id:
            asset = Asset(
                user_id=user_id,
                asset_type="video",
                file_name=file_name,
                file_size_bytes=file_size,
                s3_url=s3_url,
                mime_type="video/mp4",
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            insert_log(db, job_id, f"Created Asset record: {asset.id}")

        # Step 4: Mark SUCCESS
        update_job(
            db, job,
            status="SUCCESS",
            result_url=s3_url,
            progress_percent=100,
            completed_at=datetime.now(timezone.utc),
        )
        insert_log(db, job_id, "Download job finished successfully.")

    except Exception as e:
        insert_log(db, job_id, f"Fatal error: {e}", "ERROR")
        update_job(
            db, job,
            status="FAILED",
            error_message=str(e)[:500],
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
