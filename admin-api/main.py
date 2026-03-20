import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import timedelta

from shared_core import models, schemas, database
from shared_core.minio_utils import (
    upload_bytes_to_minio, minio_client, MINIO_BUCKET_NAME,
    delete_object_from_minio, get_object_name
)
import celery_client

# Create DB Tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Video Creator Platform API")

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Asset APIs ──────────────────────────────────────────────────────────────

@app.post("/api/assets/upload", response_model=schemas.AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = Form("video"),
    segment_name: Optional[str] = Form(None),
    db: Session = Depends(database.get_db)
):
    """
    Upload an asset file to MinIO and save metadata in the Asset table.

    asset_type: voiceover, script, bgm, segment_clip
    segment_name: e.g. '01_hook', '02_pain_point' (only for segment_clip)
    """
    try:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        uid = str(uuid.uuid4())[:8]

        # Organize files in MinIO by type
        if segment_name:
            object_name = f"assets/segments/{segment_name}/{uid}_{file.filename}"
        else:
            object_name = f"assets/{asset_type}/{uid}_{file.filename}"

        s3_url = upload_bytes_to_minio(object_name, file_bytes, file_size, file.content_type)

        # Save to Asset table
        asset = models.Asset(
            asset_type=asset_type,
            file_name=file.filename,
            file_size_bytes=file_size,
            s3_url=s3_url,
            mime_type=file.content_type,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        return asset

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/assets", response_model=List[schemas.AssetResponse])
def list_assets(
    asset_type: Optional[str] = Query(None),
    db: Session = Depends(database.get_db)
):
    """List assets with optional type filter."""
    query = db.query(models.Asset).order_by(models.Asset.created_at.desc())
    if asset_type:
        query = query.filter(models.Asset.asset_type == asset_type)
    return query.limit(200).all()


@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(database.get_db)):
    """Delete an asset from DB and MinIO."""
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        obj_name = get_object_name(asset.s3_url)
        delete_object_from_minio(obj_name)
    except Exception:
        pass  # File might already be gone from MinIO

    db.delete(asset)
    db.commit()
    return {"status": "deleted", "id": asset_id}


# ─── Legacy Upload (backwards compat) ────────────────────────────────────────

@app.post("/api/upload")
async def upload_file_legacy(file: UploadFile = File(...)):
    """Upload an asset to MinIO and return the s3:// URL (legacy endpoint)."""
    try:
        file_bytes = await file.read()
        object_name = f"uploads/{file.filename}"
        s3_url = upload_bytes_to_minio(object_name, file_bytes, len(file_bytes), file.content_type)
        return {"status": "success", "url": s3_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Job APIs ────────────────────────────────────────────────────────────────

@app.post("/api/jobs", response_model=schemas.JobResponse)
def create_job(job: schemas.JobCreate, db: Session = Depends(database.get_db)):
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

@app.get("/api/jobs/{job_id}/download")
def get_download_url(job_id: int, db: Session = Depends(database.get_db)):
    """Generate a presigned download URL for the job's output video."""
    job = db.query(models.VideoJob).filter(models.VideoJob.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.result_url:
        raise HTTPException(status_code=404, detail="No output video available")

    prefix = f"s3://{MINIO_BUCKET_NAME}/"
    if job.result_url.startswith(prefix):
        object_name = job.result_url[len(prefix):]
    else:
        raise HTTPException(status_code=400, detail="Invalid result URL format")

    try:
        url = minio_client.presigned_get_object(
            MINIO_BUCKET_NAME,
            object_name,
            expires=timedelta(hours=2)
        )
        return {"download_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
