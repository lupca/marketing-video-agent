"""
Celery worker for Video Translify jobs.
Uses shared worker_base for common infrastructure.
"""

import os
import logging
from typing import Dict, Any

from shared_core.worker_base import create_celery_app, execute_video_task
from shared_core.minio_utils import (
    download_file_from_minio, is_minio_path, get_object_name,
)
from shared_core.gpu_utils import ensure_h264_mp4

from translify_engine.analysis_engine import AnalysisEngine
from translify_engine.render_engine import RenderEngine

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_translify", worker_type="translify")


# ── Prepare Assets (translify-specific) ──────────────────────────────────────

def download_translify_assets(config_data: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """Download MinIO assets specific to translify worker."""
    input_dir = os.path.join(work_dir, "input")
    os.makedirs(input_dir, exist_ok=True)

    # config_data contains "video" URL (MinIO)
    if "video" in config_data:
        video_url = config_data["video"]
        if is_minio_path(video_url):
            obj_name = get_object_name(video_url)
            local_path = os.path.join(input_dir, os.path.basename(obj_name))
            logger.info(f"Downloading video from MinIO: {obj_name} → {local_path}")
            download_file_from_minio(obj_name, local_path)
            
            # Ensure standard H.264 MP4 format
            local_path = ensure_h264_mp4(local_path)
            config_data["video"] = local_path

    return config_data


# ── Build Function Adapter ──────────────────────────────────────────────────

def _build_translify_video(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: call new Scene-based Video-as-Data engines with local assets."""
    video_path = local_config.get("video")
    if not video_path or not os.path.exists(video_path):
        raise ValueError(f"No valid input video found in config: {video_path}")
        
    output_mp4 = os.path.join(work_dir, "output_translated.mp4")
    temp_dir = os.path.join(work_dir, "pipeline_temp")
    
    # Read extra options if any
    voice_name = local_config.get("voice_name", "vi-VN-NamMinhNeural")
    
    logger.info("🎬 [Video-as-Data Pipeline] Starting Analysis Engine...")
    analysis_engine = AnalysisEngine()
    project_db = analysis_engine.analyze(
        video_path=video_path,
        work_dir=temp_dir,
        project_id="translify_project"
    )
    
    logger.info("🎬 [Video-as-Data Pipeline] Starting Constraint-Aware Rewrite Engine...")
    from translify_engine.constraint_engine import ConstraintEngine
    constraint_engine = ConstraintEngine()
    project_db = constraint_engine.apply_constraints(
        project=project_db,
        work_dir=temp_dir
    )
    
    logger.info("🎬 [Video-as-Data Pipeline] Starting Render Engine...")
    render_engine = RenderEngine(voice_name=voice_name)
    return render_engine.render(
        project=project_db,
        original_video=video_path,
        work_dir=temp_dir,
        output_path=output_mp4
    )



# ── Celery Task ─────────────────────────────────────────────────────────────

@celery_app.task(name="worker_translify.tasks.process_video", bind=True, max_retries=2)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="translify",
        prepare_fn=download_translify_assets,
        build_fn=_build_translify_video,
        change_cwd=False,
    )
