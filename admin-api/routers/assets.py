"""Assets router — upload, list, delete."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from shared_core import models, schemas, database
from shared_core.minio_utils import upload_bytes_to_minio, delete_object_from_minio, get_object_name, get_presigned_url
import auth as auth_module

from pydantic import BaseModel

router = APIRouter(prefix="/api/assets", tags=["Assets"])


class AssetUpdate(BaseModel):
    display_name: Optional[str] = None
    folder_id: Optional[str] = None


@router.post("/upload", response_model=schemas.AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = Form("video"),
    segment_name: Optional[str] = Form(None),
    folder_path: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    try:
        file_bytes = await file.read()
        file_size = len(file_bytes)
        uid = str(uuid.uuid4())[:8]

        # 1. Resolve folder_id and MinIO path
        if folder_id:
            # Verify folder exists and belongs to current user
            folder = (
                db.query(models.MediaFolder)
                .filter(
                    models.MediaFolder.id == folder_id,
                    models.MediaFolder.user_id == current_user.id
                )
                .first()
            )
            if not folder:
                raise HTTPException(status_code=400, detail="Folder not found or access denied")
            
            object_name = f"assets/{asset_type}/folders/{folder_id}/{uid}_{file.filename}"
            file_name_db = file.filename
        elif segment_name:
            object_name = f"assets/segments/{segment_name}/{uid}_{file.filename}"
            file_name_db = file.filename
        else:
            base_folder = folder_path.strip("/") if folder_path else ""
            if base_folder:
                object_name = f"assets/{asset_type}/{base_folder}/{uid}_{file.filename}"
                file_name_db = f"{base_folder}/{file.filename}"
            else:
                object_name = f"assets/{asset_type}/{uid}_{file.filename}"
                file_name_db = file.filename

        s3_url = upload_bytes_to_minio(object_name, file_bytes, file_size, file.content_type)

        asset = models.Asset(
            user_id=current_user.id,
            asset_type=asset_type,
            file_name=file_name_db,
            display_name=file.filename,
            file_size_bytes=file_size,
            s3_url=s3_url,
            mime_type=file.content_type,
            folder_id=folder_id,
            source="upload",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        
        data = schemas.AssetResponse.model_validate(asset)
        data.full_path = get_object_name(asset.s3_url)
        data.presigned_url = get_presigned_url(data.full_path)
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AssetCreate(BaseModel):
    project_id: Optional[str] = None
    s3_url: str
    asset_type: str
    file_name: str
    mime_type: Optional[str] = None
    folder_id: Optional[str] = None


@router.post("", response_model=schemas.AssetResponse)
def create_asset_record(
    asset_in: AssetCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    try:
        # Determine display name
        display_name = asset_in.file_name.split("/")[-1]
        
        # Verify folder if provided
        if asset_in.folder_id:
            folder = (
                db.query(models.MediaFolder)
                .filter(
                    models.MediaFolder.id == asset_in.folder_id,
                    models.MediaFolder.user_id == current_user.id
                )
                .first()
            )
            if not folder:
                raise HTTPException(status_code=400, detail="Folder not found or access denied")

        # Check if asset with this s3_url already exists for this user to avoid duplicates
        existing_asset = (
            db.query(models.Asset)
            .filter(
                models.Asset.s3_url == asset_in.s3_url,
                models.Asset.user_id == current_user.id
            )
            .first()
        )
        if existing_asset:
            data = schemas.AssetResponse.model_validate(existing_asset)
            data.full_path = get_object_name(existing_asset.s3_url)
            data.presigned_url = get_presigned_url(data.full_path)
            return data

        asset = models.Asset(
            user_id=current_user.id,
            asset_type=asset_in.asset_type,
            file_name=asset_in.file_name,
            display_name=display_name,
            file_size_bytes=0,
            s3_url=asset_in.s3_url,
            mime_type=asset_in.mime_type,
            folder_id=asset_in.folder_id,
            source="generated",
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        
        data = schemas.AssetResponse.model_validate(asset)
        data.full_path = get_object_name(asset.s3_url)
        data.presigned_url = get_presigned_url(data.full_path)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[schemas.AssetResponse])
def list_assets(
    asset_type: Optional[str] = Query(None),
    folder_id: Optional[str] = Query(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    query = (
        db.query(models.Asset)
        .filter(models.Asset.user_id == current_user.id)
        .order_by(models.Asset.created_at.desc())
    )
    if asset_type:
        query = query.filter(models.Asset.asset_type == asset_type)
        
    if folder_id:
        if folder_id == "root":
            query = query.filter(models.Asset.folder_id == None)
        else:
            query = query.filter(models.Asset.folder_id == folder_id)
        
    assets = query.limit(200).all()
    results = []
    for a in assets:
        data = schemas.AssetResponse.model_validate(a)
        data.full_path = get_object_name(a.s3_url)
        data.presigned_url = get_presigned_url(data.full_path)
        results.append(data)
    return results


@router.put("/{asset_id}", response_model=schemas.AssetResponse)
def update_asset(
    asset_id: str,
    asset_update: AssetUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    asset = (
        db.query(models.Asset)
        .filter(models.Asset.id == asset_id, models.Asset.user_id == current_user.id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset_update.display_name is not None:
        if not asset_update.display_name.strip():
            raise HTTPException(status_code=400, detail="Display name cannot be empty")
        asset.display_name = asset_update.display_name.strip()

    if asset_update.folder_id is not None:
        if asset_update.folder_id != "":
            # Verify folder exists and belongs to user
            folder = (
                db.query(models.MediaFolder)
                .filter(
                    models.MediaFolder.id == asset_update.folder_id,
                    models.MediaFolder.user_id == current_user.id
                )
                .first()
            )
            if not folder:
                raise HTTPException(status_code=400, detail="Target folder not found")
            asset.folder_id = asset_update.folder_id
        else:
            asset.folder_id = None

    db.commit()
    db.refresh(asset)
    
    data = schemas.AssetResponse.model_validate(asset)
    data.full_path = get_object_name(asset.s3_url)
    data.presigned_url = get_presigned_url(data.full_path)
    return data


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    asset = (
        db.query(models.Asset)
        .filter(models.Asset.id == asset_id, models.Asset.user_id == current_user.id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Hard delete: remove from MinIO storage first
    try:
        obj_name = get_object_name(asset.s3_url)
        delete_object_from_minio(obj_name)
    except Exception as minio_err:
        # We still delete from DB but log this error
        pass

    db.delete(asset)
    db.commit()
    return {"status": "deleted", "id": asset_id}
