"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

# ── Allowed job types ─────────────────────────────────────────────────────────

VALID_JOB_TYPES = {"review", "unbox", "unbox_viral", "slideshow", "promotion", "translify", "text2img", "leader", "tts", "capcut"}



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
    draft_parameters: Optional[Dict[str, Any]] = None
    final_parameters: Optional[Dict[str, Any]] = None
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
    draft_parameters: Optional[Dict[str, Any]] = None
    final_parameters: Optional[Dict[str, Any]] = None
    progress_percent: int
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    note: Optional[str] = None

class JobUpdate(BaseModel):
    note: Optional[str] = None
    status: Optional[str] = None
    config_data: Optional[Dict[str, Any]] = None
    draft_parameters: Optional[Dict[str, Any]] = None
    final_parameters: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None


class MediaFolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None


class MediaFolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None


class MediaFolderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    parent_id: Optional[str] = None
    is_job_folder: bool
    job_id: Optional[int] = None
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
    full_path: Optional[str] = None
    display_name: Optional[str] = None
    folder_id: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime


# ── Job Logs ──────────────────────────────────────────────────────────────────

class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    log_level: str
    message: str
    created_at: datetime


# ── Download Jobs ─────────────────────────────────────────────────────────────

class DownloadJobCreate(BaseModel):
    url: str
    format: str = "video"
    custom_filename: Optional[str] = None

    @field_validator("url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()

    @field_validator("format")
    @classmethod
    def format_valid(cls, v: str) -> str:
        if v not in ("video", "audio"):
            raise ValueError("format must be 'video' or 'audio'")
        return v


class DownloadJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    source_url: str
    format_type: str
    status: str
    progress_percent: int
    result_url: Optional[str] = None
    error_message: Optional[str] = None
    custom_filename: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class DownloadJobLogResponse(BaseModel):
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


# ── Agent ───────────────────────────────────────────────────────────────────

class AgentSessionCreate(BaseModel):
    keyword: str
    video_count: int = 1
    config: Optional[Dict[str, Any]] = None

class AgentSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: str
    keyword: str
    video_count: int
    status: str
    summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class AgentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    session_id: str
    step: str
    tool_name: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    llm_reasoning: Optional[str] = None
    log_level: str
    created_at: datetime


# ── Worker Configuration (Selective Startup) ──────────────────────────────────

class WorkerConfigBase(BaseModel):
    is_enabled: bool = False
    min_replicas: int = 0
    max_replicas: int = 3
    priority: int = 0
    config_data: Optional[Dict[str, Any]] = None

class WorkerConfigUpdate(WorkerConfigBase):
    """Schema for updating an existing worker config."""
    pass

class WorkerConfigResponse(WorkerConfigBase):
    """Schema for worker config responses."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    worker_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_modified_by: Optional[str] = None

class WorkerStatusSummary(BaseModel):
    """Summary of worker statuses for the dashboard."""
    total_workers: int
    enabled_workers: int
    disabled_workers: int
    configs: List[WorkerConfigResponse]

class WorkerBatchUpdateRequest(BaseModel):
    """Request schema for batch updating multiple worker configs."""
    updates: Dict[str, bool]  # worker_type -> is_enabled


# ── System Settings ───────────────────────────────────────────────────────────

class ModelSettingsUpdate(BaseModel):
    base_url: str = ""
    model_name: str = ""

class ModelSettingsResponse(BaseModel):
    base_url: str
    model_name: str
    source: str  # "database" | "environment" | "default"


# ── TMCP Webhook Payloads ─────────────────────────────────────────────────────

class BrandContext(BaseModel):
    brand_name: str
    tone_of_voice: Optional[str] = ""
    brand_colors: Optional[List[str]] = []

class CampaignContext(BaseModel):
    campaign_name: str
    target_audience: Optional[str] = ""
    objective: Optional[str] = ""

class VariantData(BaseModel):
    title: str
    script_content: str
    media_hints: Optional[List[str]] = []
    suggested_duration: Optional[int] = 15

class TMCPPayload(BaseModel):
    source_id: str
    brand_context: BrandContext
    campaign_context: CampaignContext
    variant_data: Optional[VariantData] = None
    title: Optional[str] = None
    script_content: Optional[str] = None
    media_hints: Optional[List[str]] = []
    suggested_duration: Optional[int] = 15
    master_contents_brief: Optional[str] = ""


# ── LLM Models CRUD ───────────────────────────────────────────────────────────

class LLMModelConfig(BaseModel):
    id: str
    name: str
    base_url: str
    model_name: str
    api_key: Optional[str] = ""

class LLMModelCreate(BaseModel):
    name: str
    base_url: str
    model_name: str
    api_key: Optional[str] = ""


# ── Chat Assistant Schemas ───────────────────────────────────────────────────

class ChatMessageCreate(BaseModel):
    content: str

class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    sender: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatSessionCreate(BaseModel):
    project_id: str
    title: Optional[str] = "Cuộc hội thoại mới"
    selected_model_id: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    title: str
    selected_model_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[ChatMessageResponse]] = []

    model_config = ConfigDict(from_attributes=True)


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None
    selected_model_id: Optional[str] = None


# ── TTS Models CRUD ───────────────────────────────────────────────────────────

class TTSModelConfig(BaseModel):
    id: str
    name: str
    provider: str  # "melotts", "edge-tts", "elevenlabs"
    base_url: Optional[str] = ""
    api_key: Optional[str] = ""
    model_name: Optional[str] = ""

class TTSModelCreate(BaseModel):
    name: str
    provider: str
    base_url: Optional[str] = ""
    api_key: Optional[str] = ""
    model_name: Optional[str] = ""

