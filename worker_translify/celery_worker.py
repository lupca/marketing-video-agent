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
        
        # 1. Analysis Engine (run scene detection, vocal extraction, transcription and OCR without translation)
        logger.info("🎬 [Stage 1] Extracting scenes, vocal/BGM, and ASR/OCR...")
        analysis_engine = AnalysisEngine()
        project_db = analysis_engine.analyze(
            video_path=video_path,
            work_dir=temp_dir,
            project_id=f"proj_{job_id}",
            translate=False
        )
        update_job(db, job, progress_percent=40)
        
        # 2. Invoke Agentic LangGraph Workflow
        logger.info("🎬 [Stage 1] Initializing Agentic LangGraph Workflow...")
        from worker_translify.agent import translify_graph
        
        # Resolve user_id
        # Resolve user_id and project_name
        user_id = None
        if job.project and job.project.user_id:
            user_id = job.project.user_id
            
        project_name = ""
        # 1. Prioritize primary video asset's display name from the DB (captures user renaming on UI)
        from shared_core.models import JobAsset, Asset
        try:
            job_asset = db.query(JobAsset).filter(JobAsset.job_id == job_id).first()
            if job_asset:
                asset = db.query(Asset).filter(Asset.id == job_asset.asset_id, Asset.asset_type == "video").first()
                if asset and asset.display_name:
                    project_name = asset.display_name
        except Exception as e:
            logger.error(f"Failed to resolve asset display name: {e}")
            
        # 2. Fallback to project name
        if not project_name and job.project and job.project.name:
            project_name = job.project.name
        if not user_id:
            from shared_core.models import User
            user = db.query(User).first()
            user_id = user.id if user else None
            
        initial_state = {
            "job_id": job_id,
            "user_id": user_id,
            "original_video_path": video_path,
            "project_data": project_db,
            "glossary": [],
            "theme_summary": "",
            "pacing_violations": [],
            "trimming_attempts": {},
            "config_data": dict(config_data),
            "project_name": project_name
        }
        
        logger.info("🎬 [Stage 1] Running LangGraph Agentic Translation Graph...")
        final_state = translify_graph.invoke(initial_state)
        
        logger.info("🎬 [Stage 1] LangGraph completed successfully.")
        project_db = final_state["project_data"]
        
        # 3. Synchronize S3 & DB Persistence
        logger.info("🎬 [Stage 1] Synchronizing S3 and database assets...")
        from shared_core.minio_utils import upload_file_to_minio, is_minio_path
        from shared_core.models import Asset
        from shared_core.worker_base import get_or_create_job_folders, insert_log, update_job
        import re
        
        video_name = config_data.get("title") or config_data.get("name") or f"translify_Job_{job_id}"
        video_name_cleaned = re.sub(r'[^a-zA-Z0-9_\-\u00C0-\u1EF9]', '_', video_name)
        
        # Get project folders
        parent_folder_id, output_folder_id, _ = get_or_create_job_folders(db, job_id, user_id, video_name)
        
        # Upload & Register Vocal Wav
        vocal_local = project_db.vocal_url
        if vocal_local and os.path.exists(vocal_local) and not is_minio_path(vocal_local):
            vocal_obj = f"jobs/{job_id}_{video_name_cleaned}/vocal.wav"
            vocal_s3_url = upload_file_to_minio(vocal_obj, vocal_local)
            
            # Save to Asset library in DB
            vocal_asset = Asset(
                user_id=user_id,
                asset_type="audio",
                file_name="vocal.wav",
                display_name="separated_vocal.wav",
                file_size_bytes=os.path.getsize(vocal_local) if os.path.exists(vocal_local) else 0,
                s3_url=vocal_s3_url,
                mime_type="audio/wav",
                folder_id=parent_folder_id,
                source="generated"
            )
            db.add(vocal_asset)
            project_db.vocal_url = vocal_s3_url
            insert_log(db, job_id, f"Uploaded and registered separated vocal: {vocal_obj}")
            
        # Upload & Register BGM Wav
        bgm_local = project_db.bgm_url
        bgm_s3_url = None
        if bgm_local and os.path.exists(bgm_local) and not is_minio_path(bgm_local):
            bgm_obj = f"jobs/{job_id}_{video_name_cleaned}/bgm.wav"
            bgm_s3_url = upload_file_to_minio(bgm_obj, bgm_local)
            
            # Save to Asset library in DB
            bgm_asset = Asset(
                user_id=user_id,
                asset_type="audio",
                file_name="bgm.wav",
                display_name="separated_bgm.wav",
                file_size_bytes=os.path.getsize(bgm_local) if os.path.exists(bgm_local) else 0,
                s3_url=bgm_s3_url,
                mime_type="audio/wav",
                folder_id=parent_folder_id,
                source="generated"
            )
            db.add(bgm_asset)
            project_db.bgm_url = bgm_s3_url
            insert_log(db, job_id, f"Uploaded and registered separated BGM: {bgm_obj}")
            
        db.commit()
        
        # Prepare updated config with VideoProject JSON
        project_dict = project_db.model_dump()
        updated_config = dict(config_data)
        updated_config["project_data"] = project_dict
        if bgm_s3_url:
            updated_config["bgm"] = bgm_s3_url
        elif project_db.bgm_url:
            updated_config["bgm"] = project_db.bgm_url
            
        # Set status to WAITING_FOR_REVIEW via update_job to fire WebSocket triggers
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

