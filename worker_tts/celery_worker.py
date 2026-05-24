import os
import logging
from datetime import datetime, timezone
from shared_core.database import SessionLocal
from shared_core.models import VideoJob
from shared_core.worker_base import create_celery_app, update_job, insert_log
from engine import generate_speech_and_upload

# Initialize Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker_tts")

# Create Celery App
celery_app = create_celery_app("worker_tts", worker_type="tts")

@celery_app.task(name="worker_tts.tasks.generate_tts", bind=True)
def process_tts_job(self, job_id: int, payload: dict):
    """
    Celery task to handle Vietnamese text-to-speech generation.
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
        insert_log(db, job_id, "Starting Vietnamese Text-to-Speech generation...")

        # 3. Extract parameters from payload
        config_data = payload.get("config_data") if isinstance(payload.get("config_data"), dict) else payload
        
        text = config_data.get("text")
        speed = float(config_data.get("speed", 1.0))
        speaker = config_data.get("speaker", "VI-default")
        
        # Get project_id
        project_id = payload.get("project_id") or (job.project_id if job else "default")

        if not text:
            raise ValueError("Text content is required for TTS job")

        # 4. Generate and Upload
        insert_log(db, job_id, f"Sending text to MeloTTS: speed={speed}, speaker={speaker}...")
        update_job(db, job, progress_percent=40)
        
        result_url = generate_speech_and_upload(
            text=text,
            speed=speed,
            speaker=speaker,
            job_id=job_id,
            project_id=project_id,
            config_data=config_data
        )

        # 5. Mark SUCCESS
        update_job(
            db, job,
            status="SUCCESS",
            result_url=result_url,
            progress_percent=100,
            completed_at=datetime.now(timezone.utc)
        )
        insert_log(db, job_id, f"Speech generation successful. URL: {result_url}")
        
        return {"status": "success", "url": result_url}

    except Exception as e:
        logger.exception(f"Error processing TTS job {job_id}")
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
