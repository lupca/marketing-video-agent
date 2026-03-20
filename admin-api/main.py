import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import timedelta

from shared_core import models, schemas, database
from shared_core.minio_utils import (
    upload_bytes_to_minio, minio_client, MINIO_BUCKET_NAME,
    delete_object_from_minio, get_object_name
)
import celery_client

# Import Auth logic
import auth

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


# ─── Auth APIs ───────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/auth/login", response_model=schemas.Token)
def login(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = auth.create_access_token(data={"sub": db_user.id})
    return {"access_token": access_token, "token_type": "bearer", "user_id": db_user.id, "email": db_user.email}

@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ─── Project APIs ─────────────────────────────────────────────────────────────

@app.post("/api/projects", response_model=schemas.ProjectResponse)
def create_project(project: schemas.ProjectCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_proj = models.Project(name=project.name, description=project.description, user_id=current_user.id)
    db.add(db_proj)
    db.commit()
    db.refresh(db_proj)
    return db_proj

@app.get("/api/projects", response_model=List[schemas.ProjectResponse])
def get_projects(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    return db.query(models.Project).filter(models.Project.user_id == current_user.id).order_by(models.Project.created_at.desc()).all()

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    proj = db.query(models.Project).filter(models.Project.id == project_id, models.Project.user_id == current_user.id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # We should delete related jobs, job_logs, and job_assets first or rely on CASCADE. 
    # Since we did not setup CASCADE in the DB schema implicitly, let's delete manually.
    jobs = db.query(models.VideoJob).filter(models.VideoJob.project_id == project_id).all()
    for job in jobs:
        # Delete job_logs and job_assets
        db.query(models.JobLog).filter(models.JobLog.job_id == job.id).delete()
        db.query(models.JobAsset).filter(models.JobAsset.job_id == job.id).delete()
        db.delete(job)
    
    db.delete(proj)
    db.commit()
    return {"status": "deleted", "id": project_id}


# ─── Asset APIs ──────────────────────────────────────────────────────────────

@app.post("/api/assets/upload", response_model=schemas.AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = Form("video"),
    segment_name: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        uid = str(uuid.uuid4())[:8]

        if segment_name:
            object_name = f"assets/segments/{segment_name}/{uid}_{file.filename}"
        else:
            object_name = f"assets/{asset_type}/{uid}_{file.filename}"

        s3_url = upload_bytes_to_minio(object_name, file_bytes, file_size, file.content_type)

        asset = models.Asset(
            user_id=current_user.id,
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
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.Asset).filter(models.Asset.user_id == current_user.id).order_by(models.Asset.created_at.desc())
    if asset_type:
        query = query.filter(models.Asset.asset_type == asset_type)
    return query.limit(200).all()

@app.delete("/api/assets/{asset_id}")
def delete_asset(asset_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    asset = db.query(models.Asset).filter(models.Asset.id == asset_id, models.Asset.user_id == current_user.id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    try:
        obj_name = get_object_name(asset.s3_url)
        delete_object_from_minio(obj_name)
    except Exception:
        pass

    db.delete(asset)
    db.commit()
    return {"status": "deleted", "id": asset_id}


# ─── Job APIs ────────────────────────────────────────────────────────────────

@app.post("/api/jobs", response_model=schemas.JobResponse)
def create_job(job: schemas.JobCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Verify project ownership
    proj = db.query(models.Project).filter(models.Project.id == job.project_id, models.Project.user_id == current_user.id).first()
    if not proj:
        raise HTTPException(status_code=403, detail="Project not found or access denied")

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

    # Link assets
    if job.asset_ids:
        # Verify assets belong to user
        valid_assets = db.query(models.Asset.id).filter(models.Asset.id.in_(job.asset_ids), models.Asset.user_id == current_user.id).all()
        valid_asset_ids = [a.id for a in valid_assets]
        for aid in valid_asset_ids:
            job_asset = models.JobAsset(job_id=db_job.id, asset_id=aid)
            db.add(job_asset)
        db.commit()

    # Queue worker task
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
def get_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Jobs are joined via Project to User
    jobs = db.query(models.VideoJob).join(models.Project).filter(models.Project.user_id == current_user.id).order_by(models.VideoJob.id.desc()).offset(skip).limit(limit).all()
    return jobs

@app.get("/api/jobs/{job_id}", response_model=schemas.JobResponse)
def get_job(job_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    job = db.query(models.VideoJob).join(models.Project).filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs/{job_id}/download")
def get_download_url(job_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    job = db.query(models.VideoJob).join(models.Project).filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id).first()
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

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    job = db.query(models.VideoJob).join(models.Project).filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db.query(models.JobLog).filter(models.JobLog.job_id == job.id).delete()
    db.query(models.JobAsset).filter(models.JobAsset.job_id == job.id).delete()
    db.delete(job)
    db.commit()
    
    return {"status": "deleted", "id": job_id}

@app.get("/api/jobs/{job_id}/logs", response_model=List[schemas.JobLogResponse])
def get_job_logs(job_id: int, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    job = db.query(models.VideoJob).join(models.Project).filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    logs = db.query(models.JobLog).filter(models.JobLog.job_id == job_id).order_by(models.JobLog.created_at.asc()).all()
    return logs

# ─── System Alignment APIs (Workers & Templates) ─────────────────────────────

@app.get("/api/workers", response_model=List[schemas.WorkerNodeResponse])
def get_workers(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role != "admin" and current_user.role != "creator":
        raise HTTPException(status_code=403, detail="Not permitted")
    return db.query(models.WorkerNode).order_by(models.WorkerNode.last_heartbeat.desc()).all()

@app.get("/api/templates", response_model=List[schemas.TemplateResponse])
def get_templates(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    return db.query(models.Template).all()

@app.post("/api/templates", response_model=schemas.TemplateResponse)
def create_template(template: schemas.TemplateResponse, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Assuming TemplateResponse schema also works for creation payload here 
    # just for seeding purpose if an admin needs it.
    db_template = models.Template(
        name=template.name,
        job_type=template.job_type,
        default_config_data=template.default_config_data,
        is_active=template.is_active
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
