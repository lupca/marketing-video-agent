"""
Tools for smolagents CodeAgent.

IMPORTANT: These tools run inside the worker_agent process.
When dispatching tasks to other workers (download, video generation),
we use a lightweight Celery client that does NOT call create_celery_app()
to avoid mutating the global _worker_app_name used by heartbeat.
"""

import json
import time
import logging
from typing import Dict, Any, List

from celery import Celery
from smolagents import Tool

from shared_core.database import SessionLocal
from shared_core.models import DownloadJob, Asset, VideoJob
from shared_core.config import get_settings

# Import functions from research module directly to avoid Celery overhead
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker_research.youtube_searcher import search_youtube_shorts, search_youtube_audio
from worker_research.video_analyzer import analyze_video
from shared_core.minio_utils import download_file_from_minio, get_object_name
import tempfile
import shutil

logger = logging.getLogger(__name__)


# ── Lightweight Celery dispatch client ────────────────────────────────────────
# Separate from create_celery_app() to avoid mutating global _worker_app_name
# which would corrupt the heartbeat hostname. This client is ONLY used
# to send_task() — it never starts a worker.

_dispatch_app = None

def _get_dispatch_app() -> Celery:
    """Get or create a lightweight Celery app for dispatching tasks only."""
    global _dispatch_app
    if _dispatch_app is None:
        cfg = get_settings()
        _dispatch_app = Celery(
            "agent_dispatch",
            broker=cfg.redis.url,
            backend=cfg.redis.url,
        )
        _dispatch_app.conf.update(
            task_serializer="json",
            accept_content=["json"],
            result_serializer="json",
            broker_connection_retry_on_startup=True,
        )
    return _dispatch_app


# ── Tools ─────────────────────────────────────────────────────────────────────

class YouTubeSearchTool(Tool):
    name = "youtube_search"
    description = """Tìm kiếm YouTube shorts video theo keyword.
    Trả về danh sách các video đã được chấm điểm viral.
    Input: keyword (chuỗi string cần tìm kiếm, ví dụ 'review iphone 15')
    Output: Chuỗi JSON chứa danh sách các video gồm id, url, title, duration."""
    inputs = {
        "keyword": {
            "type": "string",
            "description": "Từ khóa cần tìm kiếm"
        }
    }
    output_type = "string"

    def forward(self, keyword: str) -> str:
        logger.info(f"Tool youtube_search called with '{keyword}'")
        try:
            results = search_youtube_shorts(keyword, count=10)
            return json.dumps(results[:5], ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

class YouTubeAudioSearchTool(Tool):
    name = "youtube_audio_search"
    description = """Tìm kiếm âm thanh/nhạc nền no-copyright trên YouTube.
    Input: keyword (chuỗi string, ví dụ 'lofi chill', 'upbeat background music')
    Output: Chuỗi JSON chứa danh sách các video gồm id, url, title, duration."""
    inputs = {
        "keyword": {
            "type": "string",
            "description": "Từ khóa tìm kiếm nhạc"
        }
    }
    output_type = "string"

    def forward(self, keyword: str) -> str:
        logger.info(f"Tool youtube_audio_search called with '{keyword}'")
        try:
            results = search_youtube_audio(keyword, count=5)
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})

class DownloadVideoTool(Tool):
    name = "download_media"
    description = """Tải video hoặc audio từ YouTube. Khi thành công trả về s3_url.
    Input: url (đường dẫn youtube), format_type (loại định dạng "video" hoặc "audio"), user_id (id người dùng sở hữu).
    Output: JSON chứa result_url (đường dẫn S3 để dùng cho các tool khác) và metadata."""
    inputs = {
        "url": {
            "type": "string",
            "description": "YouTube URL cần tải."
        },
        "format_type": {
            "type": "string",
            "description": "Định dạng cần tải: 'video' hoặc 'audio'"
        },
        "user_id": {
            "type": "string",
            "description": "User ID sở hữu file này"
        }
    }
    output_type = "string"

    def forward(self, url: str, format_type: str, user_id: str) -> str:
        logger.info(f"Tool download_media called: {url} format={format_type}")
        db = SessionLocal()
        try:
            # 1. Create Download Job in DB
            job = DownloadJob(
                user_id=user_id,
                source_url=url,
                format_type=format_type,
                status="PENDING",
                progress_percent=0
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            
            # 2. Dispatch to download worker via lightweight client
            _get_dispatch_app().send_task(
                "worker_download.tasks.process_download",
                args=[job.id, {"url": url, "format": format_type, "user_id": user_id}],
                queue="download_queue",
            )

            # 3. Poll Database waiting for completion
            max_wait_seconds = 300
            poll_interval = 5
            start_time = time.time()
            while time.time() - start_time < max_wait_seconds:
                db.expire(job)  # force re-read from DB
                db_job = db.query(DownloadJob).filter(DownloadJob.id == job.id).first()
                if not db_job:
                    return json.dumps({"error": "Job disappeared from database"})
                
                if db_job.status == "SUCCESS":
                    return json.dumps({
                        "status": "success",
                        "job_id": db_job.id,
                        "result_url": db_job.result_url
                    })
                elif db_job.status == "FAILED":
                    return json.dumps({
                        "status": "failed",
                        "error": db_job.error_message
                    })
                time.sleep(poll_interval)
            
            return json.dumps({"error": "Timeout waiting for download (300s)."})
        except Exception as e:
            return json.dumps({"error": f"Download dispatch failed: {str(e)}"})
        finally:
            db.close()


class AnalyzeVideoTool(Tool):
    name = "analyze_video"
    description = """Phân tích video từ đường dẫn s3_url.
    Input: s3_url (chuỗi string vd: s3://bucket/path.mp4)
    Output: JSON chứa report phân tích (độ phân giải, thời lượng, chuyển động, kịch bản phù hợp)."""
    inputs = {
        "s3_url": {
            "type": "string",
            "description": "Đường dẫn s3 của video"
        }
    }
    output_type = "string"

    def forward(self, s3_url: str) -> str:
        logger.info(f"Tool analyze_video called: {s3_url}")
        if not s3_url.startswith("s3://"):
            return json.dumps({"error": "Invalid S3 URL. Must start with s3://"})

        work_dir = tempfile.mkdtemp(prefix="agent_analyze_")
        try:
            obj_name = get_object_name(s3_url)
            ext = os.path.splitext(obj_name)[1] or ".mp4"
            local_path = os.path.join(work_dir, f"video{ext}")
            
            download_file_from_minio(obj_name, local_path)
            analysis = analyze_video(local_path)
            return json.dumps(analysis, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)})
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


class GenerateVideoTool(Tool):
    name = "generate_video"
    description = """Quyết định xuất video mới bằng cách giao task cho Worker cụ thể.
    Nên gọi cuối cùng sau khi đã search, download, analyze video và music.
    Input: worker_type ("promotion", "slideshow", "review", hoặc "unbox_viral"), config_data_json, user_id (string).
    Output: JSON chứa job_id của video creation job."""
    inputs = {
        "worker_type": {
            "type": "string",
            "description": "Loại worker để tạo video (promotion, slideshow, review, unbox_viral)"
        },
        "config_data_json": {
            "type": "string",
            "description": "Chuỗi JSON chứa config (vd có video_url, audio_url, text_overlay,...)"
        },
        "user_id": {
            "type": "string",
            "description": "User ID của người dùng."
        }
    }
    output_type = "string"

    def forward(self, worker_type: str, config_data_json: str, user_id: str) -> str:
        logger.info(f"Tool generate_video called: worker={worker_type}")
        db = SessionLocal()
        try:
            try:
                config_data = json.loads(config_data_json)
            except Exception:
                try:
                    import ast
                    config_data = ast.literal_eval(config_data_json)
                    if not isinstance(config_data, dict):
                        raise ValueError("Not a dictionary")
                except Exception:
                    return json.dumps({"error": "config_data_json must be valid JSON string or Python dictionary string"})

            # Validate worker_type
            valid_types = {"promotion", "slideshow", "review", "unbox_viral"}
            if worker_type not in valid_types:
                return json.dumps({"error": f"worker_type must be one of: {', '.join(sorted(valid_types))}"})

            # Auto-create or get "Agent Automation" project for the user
            from shared_core.models import Project
            project = db.query(Project).filter_by(user_id=user_id, name="Agent Automation").first()
            if not project:
                project = Project(
                    user_id=user_id, 
                    name="Agent Automation", 
                    description="Videos generated automatically by AI Agent."
                )
                db.add(project)
                db.commit()
                db.refresh(project)

            # Create video job in db
            job = VideoJob(
                job_type=worker_type,
                config_data=config_data,
                project_id=project.id,
                status="PENDING",
                progress_percent=0
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            # Dispatch to appropriate worker queue
            queue_name = "unbox_queue" if worker_type == "unbox_viral" else f"{worker_type}_queue"
            task_name = (
                "worker_unbox.tasks.process_unbox_viral" if worker_type == "unbox_viral"
                else f"worker_{worker_type}.tasks.process_video"
            )
            
            _get_dispatch_app().send_task(
                task_name,
                args=[job.id, config_data],
                queue=queue_name,
            )

            return json.dumps({"status": "success", "video_job_id": job.id})
        except Exception as e:
            return json.dumps({"error": str(e)})
        finally:
            db.close()
