"""Jobs router — create, list, get, delete, download, logs."""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from shared_core import models, schemas, database
from shared_core.minio_utils import get_minio_client, get_bucket_name
import celery_client
import auth as auth_module

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _get_user_job(job_id: int, db: Session, user_id: str):
    """Helper to find a job owned by the current user via project."""
    job = (
        db.query(models.VideoJob)
        .join(models.Project)
        .filter(models.VideoJob.id == job_id, models.Project.user_id == user_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=schemas.JobResponse)
def create_job(
    job: schemas.JobCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    # Verify project ownership
    proj = (
        db.query(models.Project)
        .filter(models.Project.id == job.project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not proj:
        raise HTTPException(status_code=403, detail="Project not found or access denied")

    db_job = models.VideoJob(
        job_type=job.job_type,
        config_data=job.config_data,
        project_id=job.project_id,
        template_id=job.template_id,
        priority=job.priority,
        status="PENDING",
        progress_percent=0,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Prepare task config
    task_config = dict(db_job.config_data) if db_job.config_data else {}

    # Link assets
    if job.asset_ids:
        valid_assets = (
            db.query(models.Asset.id)
            .filter(models.Asset.id.in_(job.asset_ids), models.Asset.user_id == current_user.id)
            .all()
        )
        for (aid,) in valid_assets:
            db.add(models.JobAsset(job_id=db_job.id, asset_id=aid))
        db.commit()

    # Queue worker task
    queue_name = f"{job.job_type}_queue"
    task_name = f"worker_{job.job_type}.tasks.process_video"
    
    if job.job_type == "unbox_viral":
        queue_name = "unbox_queue"
        task_name = "worker_unbox.tasks.process_unbox_viral"

    try:
        celery_client.celery_app.send_task(
            task_name,
            args=[db_job.id, task_config],
            queue=queue_name,
        )
    except Exception as e:
        db_job.status = "FAILED"
        db_job.error_message = f"Failed to push to queue: {str(e)}"
        db.commit()
        db.refresh(db_job)
        raise HTTPException(status_code=500, detail="Failed to queue job")

    return db_job


@router.get("", response_model=List[schemas.JobResponse])
def get_jobs(
    project_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    query = (
        db.query(models.VideoJob)
        .join(models.Project)
        .filter(models.Project.user_id == current_user.id)
    )
    if project_id:
        query = query.filter(models.Project.id == project_id)
        
    return (
        query.order_by(models.VideoJob.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{job_id}", response_model=schemas.JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return _get_user_job(job_id, db, current_user.id)


@router.get("/{job_id}/download")
def get_download_url(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = _get_user_job(job_id, db, current_user.id)
    if not job.result_url:
        raise HTTPException(status_code=404, detail="No output video available")

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


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = _get_user_job(job_id, db, current_user.id)
    # Cascade handles logs and job_assets
    db.delete(job)
    db.commit()
    return {"status": "deleted", "id": job_id}


@router.get("/{job_id}/logs", response_model=List[schemas.JobLogResponse])
def get_job_logs(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    _get_user_job(job_id, db, current_user.id)  # auth check
    return (
        db.query(models.JobLog)
        .filter(models.JobLog.job_id == job_id)
        .order_by(models.JobLog.created_at.asc())
        .all()
    )
