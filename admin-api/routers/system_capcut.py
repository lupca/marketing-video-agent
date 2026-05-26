from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from shared_core import models, database
import auth as auth_module

router = APIRouter()

# --- CapCut Settings schemas ---
class CapCutSettingsResponse(BaseModel):
    selected_model_id: str
    custom_base_url: str
    custom_model_name: str
    custom_api_key: str
    source: str

class CapCutSettingsUpdate(BaseModel):
    selected_model_id: str
    custom_base_url: Optional[str] = ""
    custom_model_name: Optional[str] = ""
    custom_api_key: Optional[str] = ""

# --- Dify Settings schemas ---
class DifySettingsResponse(BaseModel):
    base_url: str
    api_key: str
    dataset_id: str
    source: str

class DifySettingsUpdate(BaseModel):
    base_url: Optional[str] = "https://api.dify.ai/v1"
    api_key: str
    dataset_id: str

class LearnTemplateRequest(BaseModel):
    draft_id: str
    dataset_id: Optional[str] = None


@router.get("/system/capcut-settings", response_model=CapCutSettingsResponse)
def get_capcut_settings(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy cấu hình model LLM chuyên biệt cho CapCut worker."""
    from shared_core.config import get_settings
    settings = get_settings()
    
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "capcut_settings").first()
    if db_setting and db_setting.value:
        return {
            "selected_model_id": db_setting.value.get("selected_model_id", "default"),
            "custom_base_url": db_setting.value.get("custom_base_url", ""),
            "custom_model_name": db_setting.value.get("custom_model_name", ""),
            "custom_api_key": db_setting.value.get("custom_api_key", ""),
            "source": "database"
        }
    return {
        "selected_model_id": "default",
        "custom_base_url": "",
        "custom_model_name": "",
        "custom_api_key": "",
        "source": "environment"
    }


@router.put("/system/capcut-settings", response_model=CapCutSettingsResponse)
def update_capcut_settings(
    update: CapCutSettingsUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật cấu hình model LLM chuyên biệt cho CapCut worker."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "capcut_settings").first()
    if not db_setting:
        db_setting = models.SystemSetting(key="capcut_settings")
        db.add(db_setting)
    
    db_setting.value = {
        "selected_model_id": update.selected_model_id,
        "custom_base_url": update.custom_base_url or "",
        "custom_model_name": update.custom_model_name or "",
        "custom_api_key": update.custom_api_key or ""
    }
    db_setting.updated_by = current_user.id
    db.commit()
    db.refresh(db_setting)
    
    return {
        "selected_model_id": db_setting.value["selected_model_id"],
        "custom_base_url": db_setting.value["custom_base_url"],
        "custom_model_name": db_setting.value["custom_model_name"],
        "custom_api_key": db_setting.value["custom_api_key"],
        "source": "database"
    }


@router.get("/system/dify-settings", response_model=DifySettingsResponse)
def get_dify_settings(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy cấu hình Dify RAG Knowledge Base."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "dify_settings").first()
    if db_setting and db_setting.value:
        return {
            "base_url": db_setting.value.get("base_url", "https://api.dify.ai/v1"),
            "api_key": db_setting.value.get("api_key", ""),
            "dataset_id": db_setting.value.get("dataset_id", ""),
            "source": "database"
        }
    return {
        "base_url": "https://api.dify.ai/v1",
        "api_key": "",
        "dataset_id": "",
        "source": "environment"
    }


@router.put("/system/dify-settings", response_model=DifySettingsResponse)
def update_dify_settings(
    update: DifySettingsUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật cấu hình Dify RAG Knowledge Base."""
    db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "dify_settings").first()
    if not db_setting:
        db_setting = models.SystemSetting(key="dify_settings")
        db.add(db_setting)
    
    db_setting.value = {
        "base_url": update.base_url or "https://api.dify.ai/v1",
        "api_key": update.api_key,
        "dataset_id": update.dataset_id
    }
    db_setting.updated_by = current_user.id
    db.commit()
    db.refresh(db_setting)
    
    return {
        "base_url": db_setting.value["base_url"],
        "api_key": db_setting.value["api_key"],
        "dataset_id": db_setting.value["dataset_id"],
        "source": "database"
    }


@router.get("/system/capcut-drafts")
def get_capcut_drafts(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Quét các thư mục nháp CapCut có sẵn trên máy để hiển thị cho việc học template."""
    import os
    draft_folder = os.getenv("CAPCUT_DRAFT_FOLDER", "E:\\capcut\\CapCut Drafts")
    
    # Convert to WSL path if running on WSL
    is_wsl = False
    try:
        with open("/proc/version", "r") as f:
            if "microsoft" in f.read().lower():
                is_wsl = True
    except Exception:
        pass
        
    wsl_folder = draft_folder
    if is_wsl:
        wsl_folder = draft_folder.replace("\\", "/")
        if len(wsl_folder) > 1 and wsl_folder[1] == ":":
            drive = wsl_folder[0].lower()
            wsl_folder = f"/mnt/{drive}{wsl_folder[2:]}"
            
    if not os.path.exists(wsl_folder):
        return []
        
    # Get learned templates history from system settings
    learned_history = {}
    try:
        db_setting = db.query(models.SystemSetting).filter(models.SystemSetting.key == "capcut_learned_templates").first()
        if db_setting and db_setting.value:
            learned_history = db_setting.value
    except Exception:
        pass

    drafts = []
    try:
        for item in os.listdir(wsl_folder):
            item_path = os.path.join(wsl_folder, item)
            if os.path.isdir(item_path) and not item.startswith("."):
                content_file = os.path.join(item_path, "draft_content.json")
                if os.path.exists(content_file):
                    mtime = os.path.getmtime(item_path)
                    
                    history = learned_history.get(item, {})
                    drafts.append({
                        "id": item,
                        "name": item,
                        "updated_at": mtime,
                        "status": history.get("status", "idle"),
                        "error": history.get("error"),
                        "learned_at": history.get("updated_at"),
                        "template_name": history.get("template_name")
                    })
    except Exception:
        pass
        
    drafts.sort(key=lambda x: x["updated_at"], reverse=True)
    return drafts


@router.post("/system/templates/learn")
def learn_template(
    req: LearnTemplateRequest,
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Gửi task học template nháp CapCut sang Celery worker."""
    from celery import Celery
    import os
    
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_app = Celery("tasks", broker=broker_url)
    
    task = celery_app.send_task(
        "worker_capcut.tasks.learn_capcut_template",
        args=[req.draft_id, req.dataset_id],
        queue="capcut_queue"
    )
    
    return {"status": "dispatched", "task_id": task.id}
