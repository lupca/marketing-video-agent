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
        
        # Defensive Recovery: If video_url points to a non-existent local temp path,
        # recover the original MinIO URL from JobAsset database mapping.
        if video_url and not is_minio_path(video_url) and not os.path.exists(video_url):
            logger.info(f"Local video file not found at '{video_url}'. Attempting database recovery...")
            from shared_core.database import SessionLocal
            from shared_core.models import JobAsset, Asset
            from shared_core.worker_base import _current_job_id
            
            db = SessionLocal()
            try:
                if _current_job_id:
                    # Query JobAsset linked to this job
                    job_assets = db.query(JobAsset).filter(JobAsset.job_id == _current_job_id).all()
                    for ja in job_assets:
                        asset = db.query(Asset).filter(Asset.id == ja.asset_id, Asset.asset_type == "video").first()
                        if asset and asset.s3_url:
                            logger.info(f"Successfully recovered original MinIO URL from DB: {asset.s3_url}")
                            video_url = asset.s3_url
                            break
            except Exception as db_err:
                logger.error(f"Failed to recover video URL from database: {db_err}")
            finally:
                db.close()

        if video_url and is_minio_path(video_url):
            obj_name = get_object_name(video_url)
            local_path = os.path.join(input_dir, os.path.basename(obj_name))
            logger.info(f"Downloading video from MinIO: {obj_name} → {local_path}")
            download_file_from_minio(obj_name, local_path)
            
            # Ensure standard H.264 MP4 format
            local_path = ensure_h264_mp4(local_path)
            config_data["video"] = local_path

    # config_data contains custom "bgm" URL (MinIO)
    if "bgm" in config_data:
        bgm_url = config_data["bgm"]
        if bgm_url and is_minio_path(bgm_url):
            obj_name = get_object_name(bgm_url)
            local_bgm = os.path.join(input_dir, os.path.basename(obj_name))
            logger.info(f"Downloading custom BGM from MinIO: {obj_name} → {local_bgm}")
            download_file_from_minio(obj_name, local_bgm)
            config_data["bgm"] = local_bgm

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
    bgm_path = local_config.get("bgm")
    return render_engine.render(
        project=project_db,
        original_video=video_path,
        work_dir=temp_dir,
        output_path=output_mp4,
        bgm_file=bgm_path
    )



# ── Render Only Adapter ──────────────────────────────────────────────────────

def _build_render_only(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: Render-only from pre-analyzed and edited VideoProject JSON."""
    video_path = local_config.get("video")
    if not video_path or not os.path.exists(video_path):
        raise ValueError(f"No valid input video found in config: {video_path}")
        
    project_dict = local_config.get("project_data")
    if not project_dict:
        raise ValueError("No project_data (VideoProject JSON) found in config for rendering")
        
    from model.video_schema import VideoProject
    project_db = VideoProject(**project_dict)
    
    temp_dir = os.path.join(work_dir, "pipeline_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    # Run Constraint Engine again just in case (to format text lengths or auto-correct)
    logger.info("🎬 [Video-as-Data Pipeline] Applying final constraints...")
    from translify_engine.constraint_engine import ConstraintEngine
    constraint_engine = ConstraintEngine()
    project_db = constraint_engine.apply_constraints(
        project=project_db,
        work_dir=temp_dir
    )
    
    voice_name = local_config.get("voice_name", "vi-VN-NamMinhNeural")
    bgm_path = local_config.get("bgm")
    
    logger.info("🎬 [Video-as-Data Pipeline] Running Render Engine...")
    render_engine = RenderEngine(voice_name=voice_name)
    return render_engine.render(
        project=project_db,
        original_video=video_path,
        work_dir=temp_dir,
        output_path=os.path.join(work_dir, "output_translated.mp4"),
        bgm_file=bgm_path
    )


# ── Celery Tasks ────────────────────────────────────────────────────────────

@celery_app.task(name="worker_translify.tasks.process_video", bind=True, max_retries=2)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    """Standard end-to-end processing (legacy CLI/fallback)."""
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="translify",
        prepare_fn=download_translify_assets,
        build_fn=_build_translify_video,
        change_cwd=False,
    )


@celery_app.task(name="worker_translify.tasks.analyze_video", bind=True, max_retries=2)
def analyze_video(self, job_id: int, config_data: Dict[str, Any]):
    """Stage 1: Run PySceneDetect, Speech to Text, OCR, and AI Translation."""
    from shared_core.database import SessionLocal
    from shared_core.models import VideoJob
    from shared_core.worker_base import insert_log, update_job
    import tempfile
    import shutil

    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.warning(f"Job {job_id} not found in DB, skipping.")
        db.close()
        return

    update_job(db, job, status="PROCESSING", progress_percent=5)
    insert_log(db, job_id, "🎬 Stage 1: Starting Analysis Engine...")

    work_dir = tempfile.mkdtemp(prefix=f"translify_analyze_{job_id}_")
    try:
        local_config = download_translify_assets(dict(config_data), work_dir)
        video_path = local_config.get("video")
        
        temp_dir = os.path.join(work_dir, "pipeline_temp")
        
        # 1. Analysis Engine
        logger.info("🎬 [Stage 1] Extracting scenes, vocal/BGM, and ASR/OCR...")
        analysis_engine = AnalysisEngine()
        project_db = analysis_engine.analyze(
            video_path=video_path,
            work_dir=temp_dir,
            project_id=f"proj_{job_id}"
        )
        update_job(db, job, progress_percent=50)
        
        # 2. Constraint Engine (runs initial LLM translations)
        logger.info("🎬 [Stage 1] Performing initial translations & constraint-checking...")
        from translify_engine.constraint_engine import ConstraintEngine
        constraint_engine = ConstraintEngine()
        project_db = constraint_engine.apply_constraints(
            project=project_db,
            work_dir=temp_dir
        )
        update_job(db, job, progress_percent=90)
        
        # 3. Serialize VideoProject and save to config_data
        project_dict = project_db.model_dump()
        updated_config = dict(config_data)
        updated_config["project_data"] = project_dict
        
        # Set status to WAITING_FOR_REVIEW
        update_job(
            db, job, 
            config_data=updated_config, 
            status="WAITING_FOR_REVIEW", 
            progress_percent=100
        )
        insert_log(db, job_id, "🎬 Stage 1 Complete. Video is ready in database. Waiting for UI review.")
    except Exception as e:
        logger.exception("Error in analyze_video")
        insert_log(db, job_id, f"Analysis failed: {str(e)}", "ERROR")
        update_job(db, job, status="FAILED", error_message=str(e)[:500])
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()


@celery_app.task(name="worker_translify.tasks.render_video", bind=True, max_retries=2)
def render_video(self, job_id: int, config_data: Dict[str, Any]):
    """Stage 2: Generate TTS voiceovers, mix BGM, and render final output."""
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="translify",
        prepare_fn=download_translify_assets,
        build_fn=_build_render_only,
        change_cwd=False,
    )

