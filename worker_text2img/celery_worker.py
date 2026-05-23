import os
import logging
from datetime import datetime, timezone
from shared_core.database import SessionLocal
from shared_core.models import VideoJob
from shared_core.worker_base import create_celery_app, update_job, insert_log
from engine import generate_flux_image_and_upload

# Initialize Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker_text2img")

# Create Celery App
celery_app = create_celery_app("worker_text2img", worker_type="text2img")

@celery_app.task(name="worker_text2img.tasks.generate_image", bind=True)
def process_text2img_job(self, job_id: int, payload: dict):
    """
    Celery task to handle text-to-image generation.
    """
    db = SessionLocal()
    try:
        # 1. Fetch Job from DB
        job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found in database.")
            return {"status": "error", "message": "Job not found"}

        # 2. Update Status to PROCESSING
        now = datetime.now(timezone.utc)
        update_job(db, job, status="PROCESSING", started_at=now, progress_percent=10)
        insert_log(db, job_id, "Starting text-to-image generation via ComfyUI (FLUX)...")

        # 3. Extract parameters from payload (robust fallback for both flat and nested structure)
        config_data = payload.get("config_data") if isinstance(payload.get("config_data"), dict) else payload
        
        prompt = config_data.get("prompt")
        width = config_data.get("width", 1024)
        height = config_data.get("height", 1024)
        seed = config_data.get("seed")
        
        # Get project_id from payload, otherwise fallback to the database job object
        project_id = payload.get("project_id") or (job.project_id if job else "default")

        if not prompt:
            raise ValueError("Prompt is required for text2img job")

        # 4. Generate and Upload
        # This calls ComfyUI, waits for result, and uploads to MinIO
        result_url = generate_flux_image_and_upload(
            prompt, job_id, project_id, 
            width=width, height=height, seed=seed
        )

        # 5. Mark SUCCESS
        update_job(
            db, job,
            status="SUCCESS",
            result_url=result_url,
            progress_percent=100,
            completed_at=datetime.now(timezone.utc)
        )
        insert_log(db, job_id, f"Image generation successful. URL: {result_url}")
        
        return {"status": "success", "url": result_url}

    except Exception as e:
        logger.exception(f"Error processing text2img job {job_id}")
        if 'job' in locals() and job:
            insert_log(db, job_id, f"Error: {str(e)}", level="ERROR")
            update_job(
                db, job,
                status="FAILED",
                error_message=str(e)[:500],
                completed_at=datetime.now(timezone.utc)
            )
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
