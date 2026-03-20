from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class JobCreate(BaseModel):
    job_type: str
    config_data: Dict[str, Any]
    project_id: Optional[str] = None
    template_id: Optional[str] = None
    priority: Optional[int] = 0

class JobResponse(BaseModel):
    id: int
    job_type: str
    project_id: Optional[str] = None
    template_id: Optional[str] = None
    worker_id: Optional[str] = None
    status: str
    priority: int
    config_data: Dict[str, Any]
    progress_percent: int
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AssetResponse(BaseModel):
    id: str
    asset_type: Optional[str] = None
    file_name: str
    file_size_bytes: int
    s3_url: str
    mime_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
