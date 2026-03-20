import uuid
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from shared_core.database import Base

def generate_uuid():
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

    projects = relationship("Project", back_populates="user")
    assets = relationship("Asset", back_populates="user")

class Project(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="projects")
    video_jobs = relationship("VideoJob", back_populates="project")

class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    asset_type = Column(String, index=True) # video, audio, image
    file_name = Column(String, nullable=False)
    file_size_bytes = Column(BigInteger, default=0)
    s3_url = Column(String, nullable=False) # Local MinIO
    mime_type = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="assets")
    job_assets = relationship("JobAsset", back_populates="asset")

class Template(Base):
    __tablename__ = "templates"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    job_type = Column(String, index=True)
    default_config_data = Column(JSONB)
    is_active = Column(Boolean, default=True)

class VideoJob(Base):
    __tablename__ = "video_jobs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    template_id = Column(String, ForeignKey("templates.id"), nullable=True)
    worker_id = Column(String, ForeignKey("worker_nodes.id"), nullable=True)
    job_type = Column(String, index=True) # review, unbox
    status = Column(String, default="PENDING", index=True) # PENDING, PROCESSING, SUCCESS, FAILED
    priority = Column(Integer, default=0)
    config_data = Column(JSON) # fallback to normal JSON if JSONB not needed, but JSONB is better in PG
    result_url = Column(String, nullable=True) # Local path to output mp4
    error_message = Column(Text, nullable=True)
    progress_percent = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="video_jobs")
    job_assets = relationship("JobAsset", back_populates="video_job")
    logs = relationship("JobLog", back_populates="video_job")
    worker_node = relationship("WorkerNode", back_populates="video_jobs")

class JobAsset(Base):
    __tablename__ = "job_assets"
    job_id = Column(Integer, ForeignKey("video_jobs.id"), primary_key=True)
    asset_id = Column(String, ForeignKey("assets.id"), primary_key=True)

    video_job = relationship("VideoJob", back_populates="job_assets")
    asset = relationship("Asset", back_populates="job_assets")

class JobLog(Base):
    __tablename__ = "job_logs"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("video_jobs.id"), index=True)
    log_level = Column(String, default="INFO")
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video_job = relationship("VideoJob", back_populates="logs")

class WorkerNode(Base):
    __tablename__ = "worker_nodes"
    id = Column(String, primary_key=True, default=generate_uuid)
    hostname = Column(String, nullable=False)
    ip_address = Column(String, nullable=True)
    supported_types = Column(JSONB, nullable=True)
    status = Column(String, index=True, default="ONLINE")
    current_job_id = Column(Integer, nullable=True)
    last_heartbeat = Column(DateTime(timezone=True), server_default=func.now())

    video_jobs = relationship("VideoJob", back_populates="worker_node")
