import fastapi
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


def resolve_celery_task_and_queue(job_type: str) -> tuple[str, str]:
    """
    Phân giải tên Celery Task và Queue tương ứng với loại Job.
    Tập trung logic ánh xạ tại một nơi duy nhất.
    """
    queue_name = f"{job_type}_queue"
    task_name = f"worker_{job_type}.tasks.process_video"
    
    if job_type == "unbox_viral":
        queue_name = "unbox_queue"
        task_name = "worker_unbox.tasks.process_unbox_viral"
    elif job_type == "translify":
        task_name = "worker_translify.tasks.analyze_video"
    elif job_type == "agent":
        queue_name = "agent_queue"
        task_name = "worker_agent.tasks.process_tmcp_webhook"
    elif job_type == "leader":
        queue_name = "leader_queue"
        task_name = "worker_leader.tasks.process_leader_job"
    elif job_type == "text2img":
        task_name = "worker_text2img.tasks.generate_image"
    elif job_type == "tts":
        task_name = "worker_tts.tasks.generate_tts"
    elif job_type == "capcut":
        task_name = "worker_capcut.tasks.process_capcut_job"
        
    return task_name, queue_name


def get_or_create_tmcp_project(db: Session) -> models.Project:
    """Tìm hoặc tự động khởi tạo Project TMCP Outsource mặc định."""
    user = db.query(models.User).filter(models.User.role == "admin").first()
    if not user:
        user = db.query(models.User).first()
    if not user:
        raise HTTPException(
            status_code=500, detail="No users configured in database. Cannot create project."
        )

    proj = db.query(models.Project).filter(
        models.Project.name == "TMCP Outsource", 
        models.Project.user_id == user.id
    ).first()
    
    if not proj:
        proj = models.Project(
            name="TMCP Outsource", 
            description="Workspace for TMCP Outsource Integration", 
            user_id=user.id
        )
        db.add(proj)
        db.commit()
        db.refresh(proj)
    return proj



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

    # Queue worker task using centralized helper
    task_name, queue_name = resolve_celery_task_and_queue(job.job_type)

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


@router.patch("/{job_id}", response_model=schemas.JobResponse)
def update_job(
    job_id: int,
    job_update: schemas.JobUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = _get_user_job(job_id, db, current_user.id)
    
    if job_update.note is not None:
        job.note = job_update.note
        
    if job_update.priority is not None:
        job.priority = job_update.priority
        
    if job_update.config_data is not None:
        job.config_data = job_update.config_data
        
    if job_update.draft_parameters is not None:
        job.draft_parameters = job_update.draft_parameters
        
    if job_update.final_parameters is not None:
        job.final_parameters = job_update.final_parameters

    if job_update.status is not None:
        # Nếu chuyển từ DRAFT sang PENDING, đẩy task vào Celery Queue!
        if job.status == "DRAFT" and job_update.status == "PENDING":
            job.status = "PENDING"
            
            # Queue worker task using centralized helper
            task_name, queue_name = resolve_celery_task_and_queue(job.job_type)
                
            task_config = dict(job.config_data) if job.config_data else dict(job.draft_parameters) if job.draft_parameters else {}
            
            try:
                celery_client.celery_app.send_task(
                    task_name,
                    args=[job.id, task_config],
                    queue=queue_name,
                )
            except Exception as e:
                job.status = "FAILED"
                job.error_message = f"Failed to push to Celery queue: {str(e)}"
                db.commit()
                raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")
        else:
            job.status = job_update.status
        
    db.commit()
    db.refresh(job)
    return job


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


@router.get("/{job_id}/trace", response_model=List[schemas.AgentLogResponse])
def get_job_trace(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Retrieve LangGraph trace execution logs for Leader Agent."""
    _get_user_job(job_id, db, current_user.id)  # auth check
    return (
        db.query(models.AgentLog)
        .filter(models.AgentLog.job_id == job_id)
        .order_by(models.AgentLog.created_at.asc())
        .all()
    )


@router.post("/from-tmcp", response_model=schemas.JobResponse)
def create_job_from_tmcp(
    payload: schemas.TMCPPayload,
    x_tmcp_key: Optional[str] = fastapi.Header(None, alias="X-TMCP-Key"),
    db: Session = Depends(database.get_db),
):
    import os
    expected_key = os.getenv("TMCP_API_KEY", "tmcp_secret_key_123")
    if x_tmcp_key != expected_key:
         raise HTTPException(status_code=403, detail="Forbidden: Invalid X-TMCP-Key")

    # Tìm hoặc tạo project mặc định "TMCP Outsource" qua database helper
    proj = get_or_create_tmcp_project(db)

    # Tạo Job loại "leader" ở trạng thái PENDING
    db_job = models.VideoJob(
         job_type="leader",
         project_id=proj.id,
         status="PENDING",
         priority=0,
         config_data=payload.dict(),
         progress_percent=0,
         note=f"Received webhook from TMCP for variant: {payload.source_id}",
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Đẩy task xử lý webhook cho Leader Agent (worker_leader)
    task_name, queue_name = resolve_celery_task_and_queue("leader")
    try:
         celery_client.celery_app.send_task(
              task_name,
              args=[db_job.id],
              queue=queue_name,
         )
    except Exception as e:
         db_job.status = "FAILED"
         db_job.error_message = f"Failed to push to leader queue: {str(e)}"
         db.commit()
         db.refresh(db_job)
         raise HTTPException(status_code=500, detail=f"Failed to queue leader task: {str(e)}")

    return db_job
