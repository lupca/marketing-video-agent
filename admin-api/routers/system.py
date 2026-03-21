"""System router — health, workers, templates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
import auth as auth_module

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/workers", response_model=List[schemas.WorkerNodeResponse])
def get_workers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    if current_user.role not in ("admin", "creator"):
        raise HTTPException(status_code=403, detail="Not permitted")
    return db.query(models.WorkerNode).order_by(models.WorkerNode.last_heartbeat.desc()).all()


@router.get("/templates", response_model=List[schemas.TemplateResponse])
def get_templates(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return db.query(models.Template).all()


@router.post("/templates", response_model=schemas.TemplateResponse)
def create_template(
    template: schemas.TemplateCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    db_template = models.Template(
        name=template.name,
        job_type=template.job_type,
        default_config_data=template.default_config_data,
        is_active=template.is_active,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template
