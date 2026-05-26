from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared_core import models, schemas, database
import auth as auth_module

router = APIRouter(prefix="/api/user", tags=["User Preferences"])

def mask_api_key(key: str) -> str:
    if not key or len(key) < 8:
        return "********"
    return f"{key[:4]}...{key[-4:]}"

@router.get("/llm-preferences", response_model=schemas.UserLLMPreferences)
def get_user_llm_preferences(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy cấu hình AI/LLM cá nhân của User (Masked API Keys)."""
    prefs = current_user.llm_preferences or {"custom_models": [], "routing": {}}
    
    # Mask keys before sending to UI
    masked_models = []
    for m in prefs.get("custom_models", []):
        m_copy = dict(m)
        if m_copy.get("api_key"):
            m_copy["api_key"] = mask_api_key(m_copy["api_key"])
        masked_models.append(m_copy)
    
    return {
        "custom_models": masked_models,
        "routing": prefs.get("routing", {})
    }


@router.put("/llm-preferences", response_model=schemas.UserLLMPreferences)
def update_user_llm_preferences(
    prefs_in: schemas.UserLLMPreferences,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật cấu hình AI/LLM cá nhân. Chỉ cập nhật key nếu giá trị mới không phải là masked."""
    current_prefs = current_user.llm_preferences or {"custom_models": [], "routing": {}}
    
    # Logic: If UI sends a masked key (contains '...'), preserve the original key from DB
    updated_models = []
    for m_in in prefs_in.custom_models:
        m_dict = m_in.model_dump()
        
        # Check if this is an update to an existing model
        if "..." in m_dict.get("api_key", ""):
            # Find original key in DB
            original = next((old for old in current_prefs.get("custom_models", []) if old["id"] == m_dict["id"]), None)
            if original:
                m_dict["api_key"] = original.get("api_key")
        
        updated_models.append(m_dict)
    
    new_prefs = {
        "custom_models": updated_models,
        "routing": prefs_in.routing
    }
    
    current_user.llm_preferences = new_prefs
    db.commit()
    db.refresh(current_user)
    
    # Return masked version
    return get_user_llm_preferences(db, current_user)
