"""
Celery worker for Social Media Download jobs.
Uses yt-dlp to download videos/audio from URLs, uploads to MinIO, and creates Asset records.
Operates on the independent DownloadJob model (not VideoJob).
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

from shared_core.worker_base import create_celery_app
from shared_core.database import SessionLocal
from shared_core.models import DownloadJob, DownloadJobLog, Asset
from shared_core.minio_utils import ensure_bucket_exists, upload_file_to_minio
from shared_core.gpu_utils import ensure_h264_mp4

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_download", worker_type="download")


# ── DB Helpers (use DownloadJob / DownloadJobLog) ─────────────────────────────

def _update_job(db, job: DownloadJob, **kwargs) -> None:
    for key, value in kwargs.items():
        setattr(job, key, value)
    db.commit()


def _insert_log(db, job_id: int, message: str, level: str = "INFO") -> None:
    log_level = logging.INFO if level == "INFO" else logging.ERROR
    logger.log(log_level, "[DownloadJob %d] %s", job_id, message)
    db.add(DownloadJobLog(job_id=job_id, log_level=level, message=message))
    db.commit()


# ── yt-dlp Runner ────────────────────────────────────────────────────────────

def _run_ytdlp(url: str, output_dir: str, format_type: str = "video", custom_filename: str = None) -> str:
    """
    Run yt-dlp to download a video or extract audio.
    Returns the path to the downloaded file.
    """
    if custom_filename:
        # Sanitize filename and use it in template
        safe_name = "".join([c for c in custom_filename if c.isalnum() or c in (" ", ".", "_", "-")]).strip()
        output_template = os.path.join(output_dir, f"{safe_name}.%(ext)s")
    else:
        output_template = os.path.join(output_dir, "%(title).80s_%(id)s.%(ext)s")
    
    if format_type == "audio":
        cmd = [
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--no-playlist",
            "--no-overwrites",
            "-o", output_template,
            url,
        ]
    else:
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

    # Find the downloaded file
    ext = "*.mp3" if format_type == "audio" else "*.mp4"
    files = glob.glob(os.path.join(output_dir, ext))
    if not files:
        # Fallback: look for any file
        all_files = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
        if not all_files:
            raise RuntimeError(f"yt-dlp ran successfully but no files found in {output_dir}")
        return os.path.join(output_dir, all_files[0])
    return files[0]


# ── Celery Task ──────────────────────────────────────────────────────────────

@celery_app.task(name="worker_download.tasks.process_download", bind=True, max_retries=1)
def process_download(self, job_id: int, config_data: Dict[str, Any]):
    """
    Download a video/audio from URL using yt-dlp, upload to MinIO, and create an Asset.
    
    config_data:
        url: str — URL to download
        format: str — "video" or "audio"
        user_id: str — owner user ID (injected by the API)
    """
    db = SessionLocal()
    job = db.query(DownloadJob).filter(DownloadJob.id == job_id).first()
    if not job:
        logger.warning("DownloadJob %d not found in DB, skipping.", job_id)
        db.close()
        return

    url = config_data.get("url")
    user_id = config_data.get("user_id")
    format_type = config_data.get("format", "video")
    custom_filename = config_data.get("custom_filename")

    if not url:
        _update_job(db, job, status="FAILED", error_message="Missing 'url' in config_data")
        db.close()
        return

    now = datetime.now(timezone.utc)
    _update_job(db, job, status="PROCESSING", started_at=now, progress_percent=5)
    _insert_log(db, job_id, f"Starting download from: {url}")

    work_dir = tempfile.mkdtemp(prefix=f"download_job_{job_id}_")
    try:
        # Step 1: Download with yt-dlp
        _insert_log(db, job_id, "Running yt-dlp...")
        _update_job(db, job, progress_percent=10)
        downloaded_path = _run_ytdlp(url, work_dir, format_type, custom_filename)
        
        # Normalize video to H.264 MP4 if format is video
        if format_type == "video":
            _insert_log(db, job_id, "Checking video codec & normalizing to H.264 MP4 if needed...")
            downloaded_path = ensure_h264_mp4(downloaded_path)
            
        file_name = os.path.basename(downloaded_path)
        file_size = os.path.getsize(downloaded_path)
        _insert_log(db, job_id, f"Downloaded: {file_name} ({file_size} bytes)")
        _update_job(db, job, progress_percent=50)

        # Step 2: Upload to MinIO
        _insert_log(db, job_id, "Uploading to MinIO...")
        ensure_bucket_exists()
        uid = str(uuid.uuid4())[:8]
        bucket_folder = "assets/audio" if format_type == "audio" else "assets/video"
        object_name = f"{bucket_folder}/{uid}_{file_name}"
        s3_url = upload_file_to_minio(object_name, downloaded_path)
        _update_job(db, job, progress_percent=80)
        _insert_log(db, job_id, f"Uploaded to MinIO: {object_name}")

        # Step 3: Create Asset record if user_id provided
        if user_id:
            asset = Asset(
                user_id=user_id,
                asset_type="audio" if format_type == "audio" else "video",
                file_name=file_name,
                file_size_bytes=file_size,
                s3_url=s3_url,
                mime_type="audio/mpeg" if format_type == "audio" else "video/mp4",
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            _insert_log(db, job_id, f"Created Asset record: {asset.id}")

        # Step 4: Mark SUCCESS
        _update_job(
            db, job,
            status="SUCCESS",
            result_url=s3_url,
            progress_percent=100,
            completed_at=datetime.now(timezone.utc),
        )
        _insert_log(db, job_id, "Download job finished successfully.")

    except Exception as e:
        _insert_log(db, job_id, f"Fatal error: {e}", "ERROR")
        _update_job(
            db, job,
            status="FAILED",
            error_message=str(e)[:500],
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
