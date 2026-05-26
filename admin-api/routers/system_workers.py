from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from shared_core import models, schemas, database
import auth as auth_module

router = APIRouter()

@router.get("/workers", response_model=List[schemas.WorkerNodeResponse])
def get_workers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    from datetime import datetime, timezone, timedelta
    
    # Cleanup & Offline logic
    now = datetime.now(timezone.utc)
    offline_cutoff = now - timedelta(seconds=30)
    cleanup_cutoff = now - timedelta(hours=24)
    
    # Delete lost workers (> 24h)
    db.query(models.WorkerNode).filter(models.WorkerNode.last_heartbeat < cleanup_cutoff).delete()
    db.commit()
    
    # Get active lists & process virtual offline states
    workers = db.query(models.WorkerNode).order_by(models.WorkerNode.last_heartbeat.desc()).all()
    
    for w in workers:
        if w.status == "ONLINE" and w.last_heartbeat < offline_cutoff:
            w.status = "OFFLINE"
    
    return workers
