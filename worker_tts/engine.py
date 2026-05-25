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

def _get_tts_model_config_from_db(model_choice: str) -> dict | None:
    """Read a specific TTS model's config from the database 'tts_models' list."""
    try:
        from shared_core.database import SessionLocal
        from shared_core.models import SystemSetting
        with SessionLocal() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == "tts_models").first()
            if setting and setting.value and isinstance(setting.value, list):
                for m in setting.value:
                    if m.get("id") == model_choice or m.get("name") == model_choice or m.get("provider") == model_choice:
                        return m
    except Exception as e:
        logger.error(f"Error reading specific TTS model config from DB: {e}")
    return None

def generate_melotts_audio(text, speed, speaker, output_path, base_url=None):
    """
    Generator for local MeloTTS API.
    """
    url_to_use = base_url if base_url else TTS_API_URL
    tts_endpoint = f"{url_to_use.rstrip('/')}/tts"
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

def generate_elevenlabs_audio(text, speed, speaker, output_path, config_data=None, db_cfg=None):
    """
    Generator for ElevenLabs TTS API.
    """
    # 1. Resolve API Key & Model & Base URL
    api_key = ""
    model_id = "eleven_flash_v2_5"
    base_url = "https://api.elevenlabs.io"
    
    if db_cfg:
        api_key = db_cfg.get("api_key", api_key)
        model_id = db_cfg.get("model_name", model_id) or "eleven_flash_v2_5"
        base_url = db_cfg.get("base_url", base_url) or "https://api.elevenlabs.io"
        
    # Override from environment variable if set
    api_key = os.getenv("ELEVENLABS_API_KEY", api_key)
    
    # Fallback to test key if still empty
    if not api_key:
        api_key = "sk_b2c0f9915bf7b3709f1418867c8de0681650355499ea15e7"
        
    # 2. Resolve Voice ID
    # Default standard high-quality multilingual voices
    default_voice_id = "EXAVITQu4vr4xnSDxMaL"  # Bella
    voice_id = speaker
    
    # If the speaker parameter is a default MeloTTS/Edge-TTS name or VI-default, use the default voice ID
    if speaker in ["VI-default", "vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural", "default"]:
        voice_id = default_voice_id
        
    # 3. Resolve Voice Settings from config_data if present
    stability = 0.5
    similarity_boost = 0.75
    style = 0.0
    use_speaker_boost = True
    
    if config_data:
        stability = float(config_data.get("stability", config_data.get("elevenlabs_stability", stability)))
        similarity_boost = float(config_data.get("similarity_boost", config_data.get("elevenlabs_similarity_boost", similarity_boost)))
        style = float(config_data.get("style", config_data.get("elevenlabs_style", style)))
        use_speaker_boost = bool(config_data.get("use_speaker_boost", config_data.get("elevenlabs_use_speaker_boost", use_speaker_boost)))
        
        # Override model if explicitly passed
        model_id = config_data.get("elevenlabs_model", config_data.get("model_id", model_id)) or "eleven_flash_v2_5"

    # Clamp speed between 0.7 and 1.2 as supported by ElevenLabs API
    clamped_speed = max(0.7, min(1.2, speed))
    
    url = f"{base_url.rstrip('/')}/v1/text-to-speech/{voice_id}"
    
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg"
    }
    
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "speed": clamped_speed,
            "style": style,
            "use_speaker_boost": use_speaker_boost
        }
    }
    
    logger.info(f"Generating ElevenLabs audio: voice_id={voice_id}, model={model_id}, speed={clamped_speed}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=120)
        if response.status_code != 200:
            error_text = response.text
            try:
                error_json = response.json()
                error_text = error_json.get("detail", {}).get("message", error_text)
            except Exception:
                pass
            raise Exception(f"ElevenLabs API error (status {response.status_code}): {error_text}")
            
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info("Successfully generated audio from ElevenLabs.")
    except Exception as e:
        logger.error(f"Error calling ElevenLabs API: {e}")
        raise Exception(f"ElevenLabs generation failed: {str(e)}")

# Registry of supported TTS Models for easy extensibility
MODEL_PROVIDERS = {
    "melotts": generate_melotts_audio,
    "edge-tts": generate_edgetts_audio,
    "elevenlabs": generate_elevenlabs_audio
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
        
    logger.info(f"Dispatching TTS Job (Job ID: {job_id}) to Model choice: '{model_choice}'")
    
    # 1. Look up TTS model config from Database system_settings
    db_cfg = _get_tts_model_config_from_db(model_choice)
    provider = db_cfg.get("provider") if db_cfg else model_choice
    
    if provider not in MODEL_PROVIDERS:
        supported = list(MODEL_PROVIDERS.keys())
        raise ValueError(f"Unsupported model provider: '{provider}'. Supported models: {supported}")
        
    # Generate local temp file path
    file_id = str(uuid.uuid4())
    os.makedirs("/tmp", exist_ok=True)
    local_tmp_path = f"/tmp/{file_id}.mp3"
    
    try:
        # Call the selected provider
        provider_fn = MODEL_PROVIDERS[provider]
        if provider == "elevenlabs":
            provider_fn(text, speed, speaker, local_tmp_path, config_data=config_data, db_cfg=db_cfg)
        elif provider == "melotts":
            custom_base_url = db_cfg.get("base_url") if db_cfg else None
            generate_melotts_audio(text, speed, speaker, local_tmp_path, base_url=custom_base_url)
        else:
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
