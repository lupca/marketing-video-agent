"""System router — health, workers, templates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
import auth as auth_module

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/workers", response_model=List[schemas.WorkerNodeResponse])
def get_workers(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    from datetime import datetime, timezone, timedelta
    
    # ── NEW: Cleanup & Trạng thái OFFLINE ──
    now = datetime.now(timezone.utc)
    offline_cutoff = now - timedelta(seconds=30)
    cleanup_cutoff = now - timedelta(hours=24)
    
    # Xóa các worker đã mất tích hơn 24h
    db.query(models.WorkerNode).filter(models.WorkerNode.last_heartbeat < cleanup_cutoff).delete()
    db.commit()
    
    # Lấy danh sách và xử lý logic offline ảo
    workers = db.query(models.WorkerNode).order_by(models.WorkerNode.last_heartbeat.desc()).all()
    
    for w in workers:
        if w.status == "ONLINE" and w.last_heartbeat < offline_cutoff:
            w.status = "OFFLINE"
    
    return workers


@router.get("/templates", response_model=List[schemas.TemplateResponse])
def get_templates(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return db.query(models.Template).all()


@router.post("/templates", response_model=schemas.TemplateResponse)
def create_template(
    template: schemas.TemplateCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    db_template = models.Template(
        name=template.name,
        job_type=template.job_type,
        default_config_data=template.default_config_data,
        is_active=template.is_active,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.get("/system/model-settings", response_model=schemas.ModelSettingsResponse)
def get_model_settings(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy cấu hình model LLM hiện tại (Ollama/OpenAI compatible)."""
    from shared_core.config import get_settings
    settings = get_settings()
    
    # Ưu tiên: Database > Environment Variables > Default hardcoded
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "model_settings").first()
    
    if db_setting and db_setting.value:
        return {
            "base_url": db_setting.value.get("base_url", settings.ollama.base_url),
            "model_name": db_setting.value.get("model_name", settings.ollama.model_name),
            "source": "database"
        }
    
    return {
        "base_url": settings.ollama.base_url,
        "model_name": settings.ollama.model_name,
        "source": "environment"
    }


@router.put("/system/model-settings", response_model=schemas.ModelSettingsResponse)
def update_model_settings(
    update: schemas.ModelSettingsUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật cấu hình model LLM toàn hệ thống."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "model_settings").first()
    
    if not db_setting:
        db_setting = models.SystemSetting(key="model_settings")
        db.add(db_setting)
    
    db_setting.value = {
        "base_url": update.base_url,
        "model_name": update.model_name
    }
    db_setting.updated_by = current_user.id
    
    db.commit()
    db.refresh(db_setting)
    
    return {
        "base_url": db_setting.value["base_url"],
        "model_name": db_setting.value["model_name"],
        "source": "database"
    }


@router.get("/system/chat-models", response_model=List[schemas.LLMModelConfig])
def get_chat_models(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy danh sách các cấu hình model LLM từ Database."""
    import uuid
    import requests
    from shared_core.config import get_settings
    settings = get_settings()
    
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "llm_models").first()
    
    if db_setting and db_setting.value:
        return db_setting.value
        
    # Auto-seeding: Nếu chưa có trong DB, quét Ollama local và lưu cấu hình mặc định vào DB
    model_settings = db.query(models.SystemSetting).filter(models.SystemSetting.key == "model_settings").first()
    base_url = settings.ollama.base_url
    if model_settings and model_settings.value:
        base_url = model_settings.value.get("base_url", settings.ollama.base_url)
        
    discovered_models = []
    try:
        url = f"{base_url.rstrip('/')}/api/tags"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            for m in data.get("models", []):
                name = m["name"]
                discovered_models.append({
                    "id": f"ollama-{name.replace(':', '-')}",
                    "name": f"Ollama {name}",
                    "base_url": base_url,
                    "model_name": name,
                    "api_key": ""
                })
    except Exception:
        pass
        
    # Fallback mặc định nếu không quét được Ollama
    if not discovered_models:
        discovered_models = [
            {
                "id": "qwen3.5-latest",
                "name": "Ollama Qwen 3.5 (Local)",
                "base_url": "http://localhost:11434",
                "model_name": "qwen3.5:latest",
                "api_key": ""
            },
            {
                "id": "gemma4-latest",
                "name": "Ollama Gemma 4 (Local)",
                "base_url": "http://localhost:11434",
                "model_name": "gemma4:latest",
                "api_key": ""
            }
        ]
        
    # Lưu cấu hình gieo hạt (seed) này vào database
    if not db_setting:
        db_setting = models.SystemSetting(key="llm_models", value=discovered_models)
        db.add(db_setting)
    else:
        db_setting.value = discovered_models
    db.commit()
    db.refresh(db_setting)
    
    return db_setting.value


@router.post("/system/chat-models", response_model=schemas.LLMModelConfig)
def add_chat_model(
    model: schemas.LLMModelCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Thêm mới một cấu hình model LLM vào Database."""
    import uuid
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "llm_models").first()
    
    current_list = []
    if db_setting and db_setting.value:
        current_list = list(db_setting.value)
        
    new_model = {
        "id": str(uuid.uuid4()),
        "name": model.name,
        "base_url": model.base_url,
        "model_name": model.model_name,
        "api_key": model.api_key or ""
    }
    current_list.append(new_model)
    
    if not db_setting:
        db_setting = models.SystemSetting(key="llm_models", value=current_list)
        db.add(db_setting)
    else:
        db_setting.value = current_list
        db_setting.updated_by = current_user.id
        
    db.commit()
    db.refresh(db_setting)
    return new_model


@router.put("/system/chat-models/{model_id}", response_model=schemas.LLMModelConfig)
def update_chat_model(
    model_id: str,
    model: schemas.LLMModelCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật một cấu hình model LLM hiện có trong Database."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "llm_models").first()
    
    if not db_setting or not db_setting.value:
        raise HTTPException(status_code=404, detail="No models found in database.")
        
    current_list = list(db_setting.value)
    found_idx = -1
    for idx, item in enumerate(current_list):
        if item.get("id") == model_id:
            found_idx = idx
            break
            
    if found_idx == -1:
        raise HTTPException(status_code=404, detail="Model config not found.")
        
    updated_model = {
        "id": model_id,
        "name": model.name,
        "base_url": model.base_url,
        "model_name": model.model_name,
        "api_key": model.api_key or ""
    }
    current_list[found_idx] = updated_model
    
    db_setting.value = current_list
    db_setting.updated_by = current_user.id
    db.commit()
    db.refresh(db_setting)
    return updated_model


@router.delete("/system/chat-models/{model_id}")
def delete_chat_model(
    model_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Xóa một cấu hình model LLM ra khỏi Database."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "llm_models").first()
    
    if not db_setting or not db_setting.value:
        raise HTTPException(status_code=404, detail="No models found in database.")
        
    current_list = list(db_setting.value)
    found_idx = -1
    for idx, item in enumerate(current_list):
        if item.get("id") == model_id:
            found_idx = idx
            break
            
    if found_idx == -1:
        raise HTTPException(status_code=404, detail="Model config not found.")
        
    current_list.pop(found_idx)
    
    db_setting.value = current_list
    db_setting.updated_by = current_user.id
    db.commit()
    db.refresh(db_setting)
    return {"status": "deleted", "id": model_id}


@router.post("/system/chat-models/test")
def test_chat_model_connection(
    model: schemas.LLMModelCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Kiểm tra kết nối đến một cấu hình model LLM."""
    import requests
    url = f"{model.base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if model.api_key:
        headers["Authorization"] = f"Bearer {model.api_key}"
        
    payload = {
        "model": model.model_name,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        if res.status_code == 200:
            return {"status": "ok", "message": "Kết nối thành công!"}
        else:
            return {"status": "error", "message": f"Server trả về mã lỗi: {res.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Không thể kết nối: {str(e)}"}


@router.get("/system/tts-models", response_model=List[schemas.TTSModelConfig])
def get_tts_models(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy danh sách các cấu hình model TTS từ Database."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "tts_models").first()
    
    if db_setting and db_setting.value:
        return db_setting.value
        
    # Auto-seeding: Nếu chưa có trong DB, lưu cấu hình mặc định vào DB
    discovered_models = [
        {
            "id": "melotts-local",
            "name": "MeloTTS (Local)",
            "provider": "melotts",
            "base_url": "http://127.0.0.1:8000",
            "api_key": "",
            "model_name": ""
        },
        {
            "id": "edge-tts-free",
            "name": "Microsoft Edge-TTS (Free)",
            "provider": "edge-tts",
            "base_url": "",
            "api_key": "",
            "model_name": ""
        },
        {
            "id": "elevenlabs-default",
            "name": "ElevenLabs TTS",
            "provider": "elevenlabs",
            "base_url": "https://api.elevenlabs.io",
            "api_key": "sk_b2c0f9915bf7b3709f1418867c8de0681650355499ea15e7",
            "model_name": "eleven_flash_v2_5"
        }
    ]
    
    if not db_setting:
        db_setting = models.SystemSetting(key="tts_models", value=discovered_models)
        db.add(db_setting)
    else:
        db_setting.value = discovered_models
    db.commit()
    db.refresh(db_setting)
    
    return db_setting.value


@router.post("/system/tts-models", response_model=schemas.TTSModelConfig)
def add_tts_model(
    model: schemas.TTSModelCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Thêm mới một cấu hình model TTS vào Database."""
    import uuid
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "tts_models").first()
    
    current_list = []
    if db_setting and db_setting.value:
        current_list = list(db_setting.value)
        
    new_model = {
        "id": str(uuid.uuid4()),
        "name": model.name,
        "provider": model.provider,
        "base_url": model.base_url or "",
        "model_name": model.model_name or "",
        "api_key": model.api_key or ""
    }
    current_list.append(new_model)
    
    if not db_setting:
        db_setting = models.SystemSetting(key="tts_models", value=current_list)
        db.add(db_setting)
    else:
        db_setting.value = current_list
        db_setting.updated_by = current_user.id
        
    db.commit()
    db.refresh(db_setting)
    return new_model


@router.put("/system/tts-models/{model_id}", response_model=schemas.TTSModelConfig)
def update_tts_model(
    model_id: str,
    model: schemas.TTSModelCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật một cấu hình model TTS hiện có trong Database."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "tts_models").first()
    
    if not db_setting or not db_setting.value:
        raise HTTPException(status_code=404, detail="No TTS models found in database.")
        
    current_list = list(db_setting.value)
    found_idx = -1
    for idx, item in enumerate(current_list):
        if item.get("id") == model_id:
            found_idx = idx
            break
            
    if found_idx == -1:
        raise HTTPException(status_code=404, detail="TTS model config not found.")
        
    updated_model = {
        "id": model_id,
        "name": model.name,
        "provider": model.provider,
        "base_url": model.base_url or "",
        "model_name": model.model_name or "",
        "api_key": model.api_key or ""
    }
    current_list[found_idx] = updated_model
    
    db_setting.value = current_list
    db_setting.updated_by = current_user.id
    db.commit()
    db.refresh(db_setting)
    return updated_model


@router.delete("/system/tts-models/{model_id}")
def delete_tts_model(
    model_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Xóa một cấu hình model TTS ra khỏi Database."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "tts_models").first()
    
    if not db_setting or not db_setting.value:
        raise HTTPException(status_code=404, detail="No TTS models found in database.")
        
    current_list = list(db_setting.value)
    found_idx = -1
    for idx, item in enumerate(current_list):
        if item.get("id") == model_id:
            found_idx = idx
            break
            
    if found_idx == -1:
        raise HTTPException(status_code=404, detail="TTS model config not found.")
        
    current_list.pop(found_idx)
    
    db_setting.value = current_list
    db_setting.updated_by = current_user.id
    db.commit()
    db.refresh(db_setting)
    return {"status": "deleted", "id": model_id}


@router.post("/system/tts-models/test")
def test_tts_model_connection(
    model: schemas.TTSModelCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Kiểm tra kết nối đến một cấu hình model TTS."""
    import requests
    provider = model.provider
    
    if provider == "edge-tts":
        return {"status": "ok", "message": "Microsoft Edge-TTS hoạt động bình thường!"}
        
    elif provider == "melotts":
        base_url = model.base_url or "http://127.0.0.1:8000"
        url = f"{base_url.rstrip('/')}/health"
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                return {"status": "ok", "message": "Kết nối thành công đến MeloTTS!"}
            else:
                # Fallback to check root endpoint
                res_root = requests.get(f"{base_url.rstrip('/')}/", timeout=3)
                if res_root.status_code == 200 or res_root.status_code == 404:
                    return {"status": "ok", "message": "Kết nối thành công đến MeloTTS!"}
                return {"status": "error", "message": f"Server trả về mã lỗi: {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Không thể kết nối đến MeloTTS: {str(e)}"}
            
    elif provider == "elevenlabs":
        api_key = model.api_key or ""
        model_id = model.model_name or "eleven_flash_v2_5"
        # Test using a very simple, fast TTS POST request
        url = f"https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": "t",
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                return {"status": "ok", "message": "Xác thực ElevenLabs API Key thành công!"}
            else:
                err_msg = res.json().get("detail", {}).get("message", res.text)
                return {"status": "error", "message": f"ElevenLabs trả về lỗi: {err_msg}"}
        except Exception as e:
            return {"status": "error", "message": f"Không thể kết nối ElevenLabs: {str(e)}"}
            
    return {"status": "error", "message": f"Provider '{provider}' không được hỗ trợ để test."}

