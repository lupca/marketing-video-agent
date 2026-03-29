"""Downloads router — independent social media download jobs."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
from shared_core.minio_utils import get_minio_client, get_bucket_name
import celery_client
import auth as auth_module

router = APIRouter(prefix="/api/downloads", tags=["Downloads"])


@router.post("", response_model=schemas.DownloadJobResponse)
def create_download_job(
    body: schemas.DownloadJobCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    db_job = models.DownloadJob(
        user_id=current_user.id,
        source_url=body.url,
        format_type=body.format,
        custom_filename=body.custom_filename,
        status="PENDING",
        progress_percent=0,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Queue worker task
    task_config = {
        "url": body.url,
        "format": body.format,
        "user_id": current_user.id,
        "custom_filename": body.custom_filename,
    }
    try:
        celery_client.celery_app.send_task(
            "worker_download.tasks.process_download",
            args=[db_job.id, task_config],
            queue="download_queue",
        )
    except Exception as e:
        db_job.status = "FAILED"
        db_job.error_message = f"Failed to push to queue: {str(e)}"
        db.commit()
        db.refresh(db_job)
        raise HTTPException(status_code=500, detail="Failed to queue download job")

    return db_job


@router.get("", response_model=List[schemas.DownloadJobResponse])
def list_download_jobs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return (
        db.query(models.DownloadJob)
        .filter(models.DownloadJob.user_id == current_user.id)
        .order_by(models.DownloadJob.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{job_id}", response_model=schemas.DownloadJobResponse)
def get_download_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = (
        db.query(models.DownloadJob)
        .filter(models.DownloadJob.id == job_id, models.DownloadJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job


@router.delete("/{job_id}")
def delete_download_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = (
        db.query(models.DownloadJob)
        .filter(models.DownloadJob.id == job_id, models.DownloadJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    db.delete(job)
    db.commit()
    return {"status": "deleted", "id": job_id}


@router.get("/{job_id}/logs", response_model=List[schemas.DownloadJobLogResponse])
def get_download_job_logs(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    # Auth check: verify ownership
    job = (
        db.query(models.DownloadJob)
        .filter(models.DownloadJob.id == job_id, models.DownloadJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    return (
        db.query(models.DownloadJobLog)
        .filter(models.DownloadJobLog.job_id == job_id)
        .order_by(models.DownloadJobLog.created_at.asc())
        .all()
    )


@router.get("/{job_id}/download")
def get_download_job_url(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = (
        db.query(models.DownloadJob)
        .filter(models.DownloadJob.id == job_id, models.DownloadJob.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Download job not found")
    if not job.result_url:
        raise HTTPException(status_code=404, detail="No output file available")

    bucket = get_bucket_name()
    prefix = f"s3://{bucket}/"
    if not job.result_url.startswith(prefix):
        raise HTTPException(status_code=400, detail="Invalid result URL format")

    object_name = job.result_url[len(prefix):]
    try:
        url = get_minio_client().presigned_get_object(
            bucket, object_name, expires=timedelta(hours=2)
        )
        return {"download_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
