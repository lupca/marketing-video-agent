"""Projects router — CRUD for user projects."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
import auth as auth_module

router = APIRouter(prefix="/api/projects", tags=["Projects"])


@router.post("", response_model=schemas.ProjectResponse)
def create_project(
    project: schemas.ProjectCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    db_proj = models.Project(
        name=project.name,
        description=project.description,
        user_id=current_user.id,
    )
    db.add(db_proj)
    db.commit()
    db.refresh(db_proj)
    return db_proj


@router.get("", response_model=List[schemas.ProjectResponse])
def get_projects(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return (
        db.query(models.Project)
        .filter(models.Project.user_id == current_user.id)
        .order_by(models.Project.created_at.desc())
        .all()
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    proj = (
        db.query(models.Project)
        .filter(models.Project.id == project_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    # Cascade handles related jobs, logs, job_assets
    db.delete(proj)
    db.commit()
    return {"status": "deleted", "id": project_id}
