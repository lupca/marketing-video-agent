"""
SQLAlchemy ORM models for Video Creator Platform.
Uses proper cascade deletes, indexes, and JSONB for PostgreSQL.
"""

import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Use JSON base type with JSONB variant for PostgreSQL (works with SQLite for testing)
FlexibleJSON = JSON().with_variant(JSONB(), "postgresql")

from shared_core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="creator")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="projects")
    video_jobs = relationship("VideoJob", back_populates="project", cascade="all, delete-orphan")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    asset_type = Column(String, index=True)  # video, audio, image
    file_name = Column(String, nullable=False)
    file_size_bytes = Column(BigInteger, default=0)
    s3_url = Column(String, nullable=False)
    mime_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="assets")
    job_assets = relationship("JobAsset", back_populates="asset", cascade="all, delete-orphan")


class Template(Base):
    __tablename__ = "templates"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    job_type = Column(String, index=True)
    default_config_data = Column(FlexibleJSON)
    is_active = Column(Boolean, default=True)


class VideoJob(Base):
    __tablename__ = "video_jobs"
    __table_args__ = (
        Index("ix_video_jobs_project_status", "project_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    template_id = Column(String, ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    worker_id = Column(String, ForeignKey("worker_nodes.id", ondelete="SET NULL"), nullable=True)
    job_type = Column(String, index=True)  # review, unbox
    status = Column(String, default="PENDING", index=True)
    priority = Column(Integer, default=0)
    config_data = Column(FlexibleJSON)
    result_url = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    progress_percent = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    note = Column(Text, nullable=True)

    project = relationship("Project", back_populates="video_jobs")
    job_assets = relationship("JobAsset", back_populates="video_job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="video_job", cascade="all, delete-orphan")
    worker_node = relationship("WorkerNode", back_populates="video_jobs")


class JobAsset(Base):
    __tablename__ = "job_assets"

    job_id = Column(Integer, ForeignKey("video_jobs.id", ondelete="CASCADE"), primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)

    video_job = relationship("VideoJob", back_populates="job_assets")
    asset = relationship("Asset", back_populates="job_assets")


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("video_jobs.id", ondelete="CASCADE"), index=True)
    log_level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video_job = relationship("VideoJob", back_populates="logs")


class WorkerNode(Base):
    __tablename__ = "worker_nodes"

    id = Column(String, primary_key=True, default=generate_uuid)
    hostname = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    supported_types = Column(FlexibleJSON, nullable=True)
    status = Column(String, index=True, default="ONLINE")
    current_job_id = Column(Integer, nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())

    video_jobs = relationship("VideoJob", back_populates="worker_node")


class DownloadJob(Base):
    __tablename__ = "download_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_url = Column(String, nullable=False)
    format_type = Column(String, default="video")  # video or audio
    status = Column(String, default="PENDING", index=True)
    progress_percent = Column(Integer, default=0)
    result_url = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    custom_filename = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    logs = relationship("DownloadJobLog", back_populates="download_job", cascade="all, delete-orphan")


class DownloadJobLog(Base):
    __tablename__ = "download_job_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("download_jobs.id", ondelete="CASCADE"), index=True)
    log_level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    download_job = relationship("DownloadJob", back_populates="logs")


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    keyword = Column(String, nullable=False)
    video_count = Column(Integer, default=1)
    status = Column(String, default="PENDING")  # PENDING, RUNNING, COMPLETED, FAILED
    summary = Column(Text, nullable=True)  # kết quả tổng hợp từ Agent
    config = Column(FlexibleJSON, nullable=True)  # cấu hình tùy chọn
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User")
    logs = relationship("AgentLog", back_populates="session", cascade="all, delete-orphan")


class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True)
    step = Column(String, nullable=False)         # "search", "download", "analyze", "decide", "generate"
    tool_name = Column(String, nullable=True)
    input_data = Column(FlexibleJSON, nullable=True)
    output_data = Column(FlexibleJSON, nullable=True)
    llm_reasoning = Column(Text, nullable=True)    # LLM reasoning trace
    log_level = Column(String, default="INFO")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    session = relationship("AgentSession", back_populates="logs")


class WorkerConfig(Base):
    """
    Configuration for selective worker enablement and scaling.
    Allows administrators to enable/disable worker types via API.
    """
    __tablename__ = "worker_configs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    worker_type = Column(String, unique=True, index=True, nullable=False)  # review, unbox, research, agent, etc.
    is_enabled = Column(Boolean, default=False)
    min_replicas = Column(Integer, default=0)
    max_replicas = Column(Integer, default=3)
    priority = Column(Integer, default=0)
    config_data = Column(FlexibleJSON, nullable=True)
    last_modified_by = Column(String, nullable=True)  # User ID who last changed this
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
