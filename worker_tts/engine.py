import os
import json
import time
import logging
import requests
import uuid
import asyncio
import edge_tts
from shared_core.minio_utils import upload_file_to_minio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MeloTTS API Endpoint configuration (from env or fallback to local WSL/host port 8000)
TTS_API_URL = os.getenv("TTS_API_URL", "http://127.0.0.1:8000")

def generate_melotts_audio(text, speed, speaker, output_path):
    """
    Generator for local MeloTTS API.
    """
    tts_endpoint = f"{TTS_API_URL}/tts"
    payload = {
        "text": text,
        "speed": speed,
        "speaker": speaker
    }
    
    logger.info(f"Generating audio using MeloTTS API at {tts_endpoint} (speaker: {speaker}, speed: {speed})")
    
    try:
        response = requests.post(tts_endpoint, json=payload, stream=True, timeout=300)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error calling MeloTTS API: {e}")
        raise Exception(f"Could not connect to MeloTTS API: {str(e)}")
        
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    logger.info("Successfully downloaded audio from MeloTTS.")

async def _edge_tts_async(text, speaker, speed, output_path):
    """
    Asynchronous runner for edge-tts generation.
    """
    # Map float speed to Edge-TTS rate string format (+XX% or -XX%)
    if speed >= 1.0:
        percent = int((speed - 1.0) * 100)
        rate_str = f"+{percent}%"
    else:
        percent = int((1.0 - speed) * 100)
        rate_str = f"-{percent}%"
        
    # Standard fallback to HoaiMy if an invalid voice is provided
    valid_voices = ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
    voice = speaker if speaker in valid_voices else "vi-VN-HoaiMyNeural"
    
    logger.info(f"Generating Edge-TTS audio: voice={voice}, rate={rate_str}")
    communicate = edge_tts.Communicate(text, voice, rate=rate_str)
    await communicate.save(output_path)

def generate_edgetts_audio(text, speed, speaker, output_path):
    """
    Generator for Microsoft Edge-TTS (Free, no keys needed).
    """
    try:
        asyncio.run(_edge_tts_async(text, speaker, speed, output_path))
        logger.info("Successfully generated audio from Edge-TTS.")
    except Exception as e:
        logger.error(f"Error generating Edge-TTS: {e}")
        raise Exception(f"Edge-TTS generation failed: {str(e)}")

# Registry of supported TTS Models for easy extensibility
MODEL_PROVIDERS = {
    "melotts": generate_melotts_audio,
    "edge-tts": generate_edgetts_audio
}

def generate_speech_and_upload(text, speed=1.0, speaker="VI-default", job_id=None, project_id=None, config_data=None):
    """
    Core coordinator: Resolves TTS model -> Generates audio -> Uploads to MinIO -> DB Register -> Cleanup.
    """
    if not text:
        raise ValueError("Text content is required for TTS job")
        
    # Resolve Model Choice (defaults to 'melotts' for backward compatibility)
    model_choice = "melotts"
    if config_data and "model" in config_data:
        model_choice = config_data.get("model")
        
    logger.info(f"Dispatching TTS Job (Job ID: {job_id}) to Model: '{model_choice}'")
    
    if model_choice not in MODEL_PROVIDERS:
        supported = list(MODEL_PROVIDERS.keys())
        raise ValueError(f"Unsupported model: '{model_choice}'. Supported models: {supported}")
        
    # Generate local temp file path
    file_id = str(uuid.uuid4())
    os.makedirs("/tmp", exist_ok=True)
    local_tmp_path = f"/tmp/{file_id}.mp3"
    
    try:
        # Call the selected provider
        provider_fn = MODEL_PROVIDERS[model_choice]
        provider_fn(text, speed, speaker, local_tmp_path)
        
        # Upload to MinIO & register in Database (PostgreSQL)
        from shared_core.database import SessionLocal
        from shared_core.models import VideoJob, Asset
        from shared_core.worker_base import get_or_create_job_folders
        
        db = SessionLocal()
        user_id = None
        parent_folder_id = None
        output_folder_id = None
        video_name_cleaned = f"Job_{job_id}"
        
        try:
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job and job.project:
                user_id = job.project.user_id
                
            video_name = "TTS_Audio"
            if config_data:
                video_name = config_data.get("title") or config_data.get("name") or f"TTS_{job_id}"
                
            if user_id and job_id:
                parent_folder_id, output_folder_id, video_name_cleaned = get_or_create_job_folders(db, job_id, user_id, video_name)
        except Exception as db_err:
            logger.error(f"Database resolution error: {db_err}")
            
        # Determine MinIO upload path
        timestamp = int(time.time())
        if parent_folder_id and output_folder_id:
            object_name = f"jobs/{job_id}_{video_name_cleaned}/output/tts_{job_id}_{timestamp}.mp3"
        else:
            object_name = f"projects/{project_id or 'default'}/audio/tts_{job_id or file_id}_{timestamp}.mp3"
            
        # Upload to MinIO
        s3_uri = upload_file_to_minio(object_name, local_tmp_path)
        logger.info(f"Uploaded audio to MinIO: {s3_uri}")
        
        # Register Asset
        if user_id:
            try:
                file_size = os.path.getsize(local_tmp_path)
                asset = Asset(
                    user_id=user_id,
                    asset_type="audio",
                    file_name=os.path.basename(object_name),
                    display_name=os.path.basename(object_name),
                    file_size_bytes=file_size,
                    s3_url=s3_uri,
                    mime_type="audio/mpeg",
                    folder_id=output_folder_id,
                    source="generated"
                )
                db.add(asset)
                db.commit()
                logger.info(f"Successfully registered TTS audio asset in database.")
            except Exception as asset_err:
                logger.error(f"Failed to register asset in DB: {asset_err}")
                
        db.close()
        
        # Cleanup local file
        if os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)
            
        return s3_uri
        
    except Exception as e:
        logger.error(f"Error handling audio generation/upload: {e}")
        if os.path.exists(local_tmp_path):
            os.remove(local_tmp_path)
        raise Exception(f"Failed to process and upload TTS audio: {str(e)}")
