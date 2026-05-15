"""
Worker Configuration Router.
Allows administrators to enable/disable specific worker types.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict

from shared_core import models, schemas, database
import auth as auth_module
import worker_spawner

router = APIRouter(prefix="/api/worker-config", tags=["System / Workers"])

@router.get("/", response_model=schemas.WorkerStatusSummary)
def get_all_worker_configs(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user)
):
    """Lấy danh sách tất cả cấu hình workers và thống kê nhanh."""
    configs = db.query(models.WorkerConfig).order_by(models.WorkerConfig.worker_type).all()
    
    total = len(configs)
    enabled = sum(1 for c in configs if c.is_enabled)
    
    return {
        "total_workers": total,
        "enabled_workers": enabled,
        "disabled_workers": total - enabled,
        "configs": configs
    }

@router.get("/{worker_type}", response_model=schemas.WorkerConfigResponse)
def get_worker_config(
    worker_type: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user)
):
    """Lấy chi tiết cấu hình của một worker type cụ thể."""
    config = db.query(models.WorkerConfig).filter(
        models.WorkerConfig.worker_type == worker_type.lower()
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Worker config for '{worker_type}' not found")
    
    return config

@router.put("/{worker_type}", response_model=schemas.WorkerConfigResponse)
def update_worker_config(
    worker_type: str,
    update: schemas.WorkerConfigUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user)
):
    """Cập nhật cấu hình cho một worker."""
    config = db.query(models.WorkerConfig).filter(
        models.WorkerConfig.worker_type == worker_type.lower()
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Worker config for '{worker_type}' not found")
    
    for field, value in update.model_dump().items():
        setattr(config, field, value)
    
    config.last_modified_by = current_user.id
    db.commit()
    db.refresh(config)
    return config

@router.post("/{worker_type}/enable", response_model=schemas.WorkerConfigResponse)
def enable_worker(
    worker_type: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user)
):
    """Bật worker type cụ thể."""
    config = db.query(models.WorkerConfig).filter(
        models.WorkerConfig.worker_type == worker_type.lower()
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Worker config for '{worker_type}' not found")
    
    config.is_enabled = True
    config.last_modified_by = current_user.id
    db.commit()
    db.refresh(config)
    
    # Actually start the worker process
    worker_spawner.start_worker(worker_type.lower())
    
    return config

@router.post("/{worker_type}/disable", response_model=schemas.WorkerConfigResponse)
def disable_worker(
    worker_type: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user)
):
    """Tắt worker type cụ thể."""
    config = db.query(models.WorkerConfig).filter(
        models.WorkerConfig.worker_type == worker_type.lower()
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail=f"Worker config for '{worker_type}' not found")
    
    config.is_enabled = False
    config.last_modified_by = current_user.id
    db.commit()
    db.refresh(config)
    
    # Actually stop the worker process
    worker_spawner.stop_worker(worker_type.lower())
    
    return config

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

def _batch_process_spawning(updates: Dict[str, bool]):
    """Background task to handle spawning/killing workers."""
    for wtype, enabled in updates.items():
        if enabled:
            worker_spawner.start_worker(wtype.lower())
        else:
            worker_spawner.stop_worker(wtype.lower())

@router.post("/batch/update")
def batch_update_workers(
    request: schemas.WorkerBatchUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user)
):
    """Cập nhật trạng thái cho nhiều worker cùng lúc."""
    updated = []
    for wtype, enabled in request.updates.items():
        config = db.query(models.WorkerConfig).filter(
            models.WorkerConfig.worker_type == wtype.lower()
        ).first()
        if config:
            config.is_enabled = enabled
            config.last_modified_by = current_user.id
            updated.append(wtype)
    
    db.commit()
    
    # Run process management in background to avoid blocking API
    background_tasks.add_task(_batch_process_spawning, request.updates)
    
    return {"status": "success", "updated_workers": updated}
