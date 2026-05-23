"""Folders router — CRUD operations and recursive hard delete."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from shared_core import models, schemas, database
from shared_core.minio_utils import delete_object_from_minio, get_object_name
import auth as auth_module

router = APIRouter(prefix="/api/folders", tags=["Folders"])


def _delete_folder_recursively(db: Session, folder_id: str, user_id: str):
    """Helper function to recursively delete a folder, its subfolders, and hard delete all assets from MinIO."""
    folder = (
        db.query(models.MediaFolder)
        .filter(models.MediaFolder.id == folder_id, models.MediaFolder.user_id == user_id)
        .first()
    )
    if not folder:
        return

    # 1. Recurse into subfolders
    children = (
        db.query(models.MediaFolder)
        .filter(models.MediaFolder.parent_id == folder_id, models.MediaFolder.user_id == user_id)
        .all()
    )
    for child in children:
        _delete_folder_recursively(db, child.id, user_id)

    # 2. Query all assets inside this specific folder
    assets = (
        db.query(models.Asset)
        .filter(models.Asset.folder_id == folder_id, models.Asset.user_id == user_id)
        .all()
    )

    # 3. Hard delete assets physically from MinIO
    for asset in assets:
        try:
            obj_name = get_object_name(asset.s3_url)
            delete_object_from_minio(obj_name)
        except Exception:
            pass  # Best-effort delete
        db.delete(asset)

    # 4. Delete the folder record itself from DB
    db.delete(folder)
    db.commit()


@router.post("", response_model=schemas.MediaFolderResponse)
def create_folder(
    folder_create: schemas.MediaFolderCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    # Verify parent folder belongs to user
    if folder_create.parent_id:
        parent = (
            db.query(models.MediaFolder)
            .filter(
                models.MediaFolder.id == folder_create.parent_id,
                models.MediaFolder.user_id == current_user.id
            )
            .first()
        )
        if not parent:
            raise HTTPException(status_code=400, detail="Parent folder not found or access denied")

    folder = models.MediaFolder(
        user_id=current_user.id,
        name=folder_create.name,
        parent_id=folder_create.parent_id,
        is_job_folder=False,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("", response_model=List[schemas.MediaFolderResponse])
def list_folders(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return (
        db.query(models.MediaFolder)
        .filter(models.MediaFolder.user_id == current_user.id)
        .order_by(models.MediaFolder.created_at.desc())
        .all()
    )


@router.get("/{folder_id}", response_model=schemas.MediaFolderResponse)
def get_folder(
    folder_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    folder = (
        db.query(models.MediaFolder)
        .filter(models.MediaFolder.id == folder_id, models.MediaFolder.user_id == current_user.id)
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder


@router.put("/{folder_id}", response_model=schemas.MediaFolderResponse)
def update_folder(
    folder_id: str,
    folder_update: schemas.MediaFolderUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    folder = (
        db.query(models.MediaFolder)
        .filter(models.MediaFolder.id == folder_id, models.MediaFolder.user_id == current_user.id)
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Prevent updating folder that is locked or bound to a job unless necessary
    # (Optional safeguard: if folder.is_job_folder: pass/raise but let's allow renaming)

    if folder_update.name is not None:
        if not folder_update.name.strip():
            raise HTTPException(status_code=400, detail="Folder name cannot be empty")
        folder.name = folder_update.name.strip()

    if folder_update.parent_id is not None:
        # Check cyclic redundancy
        if folder_update.parent_id == folder_id:
            raise HTTPException(status_code=400, detail="Folder cannot be its own parent")
            
        # Verify parent belongs to user
        if folder_update.parent_id != "":
            parent = (
                db.query(models.MediaFolder)
                .filter(
                    models.MediaFolder.id == folder_update.parent_id,
                    models.MediaFolder.user_id == current_user.id
                )
                .first()
            )
            if not parent:
                raise HTTPException(status_code=400, detail="Parent folder not found")
            folder.parent_id = folder_update.parent_id
        else:
            folder.parent_id = None

    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    folder = (
        db.query(models.MediaFolder)
        .filter(models.MediaFolder.id == folder_id, models.MediaFolder.user_id == current_user.id)
        .first()
    )
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Perform recursive hard delete of subfolders, files, and DB records
    try:
        _delete_folder_recursively(db, folder_id, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recursive delete failed: {str(e)}")

    return {"status": "deleted", "id": folder_id}
