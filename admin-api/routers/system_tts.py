from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from shared_core import models, schemas, database
import auth as auth_module

router = APIRouter()

@router.get("/system/tts-models", response_model=List[schemas.TTSModelConfig])
def get_tts_models(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy danh sách các cấu hình model TTS từ Database."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "tts_models").first()
    
    if db_setting and db_setting.value:
        return db_setting.value
        
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
                res_root = requests.get(f"{base_url.rstrip('/')}/", timeout=3)
                if res_root.status_code == 200 or res_root.status_code == 404:
                    return {"status": "ok", "message": "Kết nối thành công đến MeloTTS!"}
                return {"status": "error", "message": f"Server trả về mã lỗi: {res.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Không thể kết nối đến MeloTTS: {str(e)}"}
            
    elif provider == "elevenlabs":
        api_key = model.api_key or ""
        model_id = model.model_name or "eleven_flash_v2_5"
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
