import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
from shared_core.minio_utils import upload_bytes_to_minio
import celery_client

# Create DB Tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Video Creator Platform API")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload an asset to MinIO and return the s3:// URL."""
    try:
        file_bytes = await file.read()
        object_name = f"uploads/{file.filename}"
        s3_url = upload_bytes_to_minio(object_name, file_bytes, len(file_bytes), file.content_type)
        return {"status": "success", "url": s3_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs", response_model=schemas.JobResponse)
def create_job(job: schemas.JobCreate, db: Session = Depends(database.get_db)):
    # 1. Save job to database with status PENDING
    db_job = models.VideoJob(
        job_type=job.job_type,
        config_data=job.config_data,
        project_id=job.project_id,
        template_id=job.template_id,
        priority=job.priority,
        status="PENDING",
        progress_percent=0
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # 2. Push task to the correct Queue via Celery
    queue_name = f"{job.job_type}_queue"
    try:
        celery_client.celery_app.send_task(
            f"worker_{job.job_type}.tasks.process_video",
            args=[db_job.id, db_job.config_data],
            queue=queue_name
        )
    except Exception as e:
        db_job.status = "FAILED"
        db_job.error_message = f"Failed to push to queue: {str(e)}"
        db.commit()
        db.refresh(db_job)
        raise HTTPException(status_code=500, detail="Failed to queue job")

    return db_job

@app.get("/api/jobs", response_model=List[schemas.JobResponse])
def get_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    jobs = db.query(models.VideoJob).order_by(models.VideoJob.id.desc()).offset(skip).limit(limit).all()
    return jobs

@app.get("/api/jobs/{job_id}", response_model=schemas.JobResponse)
def get_job(job_id: int, db: Session = Depends(database.get_db)):
    job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
