"""Assets router — upload, list, delete."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from shared_core import models, schemas, database
from shared_core.minio_utils import upload_bytes_to_minio, delete_object_from_minio, get_object_name
import auth as auth_module

router = APIRouter(prefix="/api/assets", tags=["Assets"])


@router.post("/upload", response_model=schemas.AssetResponse)
async def upload_asset(
    file: UploadFile = File(...),
    asset_type: str = Form("video"),
    segment_name: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
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


@router.get("", response_model=List[schemas.AssetResponse])
def list_assets(
    asset_type: Optional[str] = Query(None),
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
    return query.limit(200).all()


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

    # Best-effort delete from MinIO
    try:
        obj_name = get_object_name(asset.s3_url)
        delete_object_from_minio(obj_name)
    except Exception:
        pass

    db.delete(asset)
    db.commit()
    return {"status": "deleted", "id": asset_id}
