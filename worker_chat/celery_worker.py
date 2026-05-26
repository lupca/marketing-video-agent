import os
import logging
from datetime import datetime, timezone
from shared_core.database import SessionLocal
from shared_core.models import VideoJob
from shared_core.worker_base import create_celery_app, update_job, insert_log
from engine import generate_chat_response

# Initialize Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker_chat")

# Create Celery App
celery_app = create_celery_app("worker_chat", worker_type="chat")

@celery_app.task(name="worker_chat.tasks.process_chat", bind=True)
def process_chat(self, job_id: int, payload: dict):
    """
    Celery task to handle AI chat assistance jobs using Ollama.
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
        insert_log(db, job_id, "Processing AI Chat Assistant query...")

        # 3. Extract parameters from payload
        config_data = payload.get("config_data") if isinstance(payload.get("config_data"), dict) else payload
        
        # Assemble message history
        history = config_data.get("history", [])
        current_message = config_data.get("text", "")
        model_id = config_data.get("model")
        
        # Construct OpenAI messages format
        messages = []
        for msg in history:
            sender = msg.get("sender")
            text = msg.get("text", "")
            if sender == "user":
                messages.append({"role": "user", "content": text})
            elif sender == "ai":
                messages.append({"role": "assistant", "content": text})
                
        # Append current user prompt
        messages.append({"role": "user", "content": current_message})

        if not current_message:
            raise ValueError("Query text is required for chat job")

        # 4. Generate AI response
        user_id = job.project.user_id if job.project else None
        insert_log(db, job_id, f"Calling LLM chat (user_id={user_id})...")
        update_job(db, job, progress_percent=50)
        
        ai_response = generate_chat_response(messages=messages, user_id=user_id, model_id=model_id)

        # 5. Mark SUCCESS & Save Response inside 'note'
        update_job(
            db, job,
            status="SUCCESS",
            result_url="ai_chat_response",
            note=ai_response,  # Save the full AI markdown response here!
            progress_percent=100,
            completed_at=datetime.now(timezone.utc)
        )
        insert_log(db, job_id, f"AI Assistant replied successfully (response length: {len(ai_response)} chars)")
        
        return {"status": "success", "response": ai_response}

    except Exception as e:
        logger.exception(f"Error processing Chat job {job_id}")
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
