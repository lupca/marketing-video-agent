"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

# ── Allowed job types ─────────────────────────────────────────────────────────

VALID_JOB_TYPES = {"review", "unbox"}


# ── Auth ──────────────────────────────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


# ── Projects ─────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Project name cannot be empty")
        return v.strip()


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    jobs_count: int = 0


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    job_type: str
    config_data: Dict[str, Any]
    project_id: str
    template_id: Optional[str] = None
    priority: Optional[int] = 0
    asset_ids: List[str] = []

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in VALID_JOB_TYPES:
            raise ValueError(f"job_type must be one of: {', '.join(sorted(VALID_JOB_TYPES))}")
        return v


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


# ── Assets ────────────────────────────────────────────────────────────────────

class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_type: Optional[str] = None
    file_name: str
    file_size_bytes: int
    s3_url: str
    presigned_url: Optional[str] = None
    mime_type: Optional[str] = None
    created_at: datetime


# ── Job Logs ──────────────────────────────────────────────────────────────────

class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    log_level: str
    message: str
    created_at: datetime


# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    """Schema for creating a new template."""
    name: str
    job_type: str
    default_config_data: dict
    is_active: bool = True

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in VALID_JOB_TYPES:
            raise ValueError(f"job_type must be one of: {', '.join(sorted(VALID_JOB_TYPES))}")
        return v


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    job_type: str
    default_config_data: dict
    is_active: bool


# ── Workers ───────────────────────────────────────────────────────────────────

class WorkerNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hostname: str
    ip_address: Optional[str] = None
    status: str
    current_job_id: Optional[int] = None
    last_heartbeat: datetime


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    """Generic wrapper for paginated list responses."""
    items: List[Any]
    total: int
    skip: int
    limit: int
