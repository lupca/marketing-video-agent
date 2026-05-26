"""
LLM Resolver — Centralized logic for resolving the appropriate LLM model and credentials.
Implements the 5-tier hierarchical fallback:
User Override -> Global Feature Routing -> Global Default -> Env Default
"""

import logging
from typing import Dict, Any, Optional
from shared_core.database import SessionLocal
from shared_core.models import User, SystemSetting
from shared_core.config import get_settings
from shared_core.constants import LLMFeature

logger = logging.getLogger(__name__)

def resolve_llm_config(user_id: Optional[str], feature_key: str) -> Dict[str, Any]:
    """
    Resolves base_url, api_key, and model_name for a given feature and user.
    Strict Priority:
    1. User Personal Override (BYOK)
    2. Global Feature Routing (DB)
    3. Global System Default (DB)
    4. Environment Fallback (Only if DB is empty)
    """
    settings = get_settings()
    db = SessionLocal()
    
    # Pre-strip ENV defaults just in case
    env_default = {
        "base_url": (settings.ollama.base_url or "").strip(),
        "model_name": (settings.ollama.model_name or "").strip(),
        "api_key": "",
        "provider": "ollama",
        "source": "environment_default"
    }

    def _format_res(m_obj, source):
        b_url = (m_obj.get("base_url") or "").strip()
        m_name = (m_obj.get("model_name") or "").strip()
        a_key = (m_obj.get("api_key") or "").strip()
        p = m_obj.get("provider")
        if not p:
            p = "ollama" if "ollama" in b_url.lower() or "11434" in b_url else "openai"
        return {
            "base_url": b_url,
            "model_name": m_name,
            "api_key": a_key,
            "provider": p,
            "source": source
        }

    try:
        # 1. Fetch Global Settings
        global_models_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm_models").first()
        global_routing_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm_routing").first()
        
        global_models = global_models_setting.value if global_models_setting and global_models_setting.value else []
        global_routing = global_routing_setting.value if global_routing_setting and global_routing_setting.value else {}

        # Pre-resolve the "Global Default Model" from DB if it exists
        db_default_model = None
        db_default_id = global_routing.get("default_model_id") or global_routing.get("default")
        if db_default_id:
            db_default_model = next((m for m in global_models if m.get("id") == db_default_id), None)

        # 2. Check User-Level Preferences (BYOK & Personal Routing)
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.llm_preferences:
                user_routing = user.llm_preferences.get("routing", {})
                model_id = user_routing.get(feature_key)
                
                if model_id:
                    # User picked a custom model
                    custom_models = user.llm_preferences.get("custom_models", [])
                    for m in custom_models:
                        if m.get("id") == model_id:
                            return _format_res(m, "user_custom")
                    # User picked a system model
                    for m in global_models:
                        if m.get("id") == model_id:
                            return _format_res(m, "user_selected_global")

        # 3. Check Global Feature Routing (Tier 3)
        model_id = global_routing.get("feature_routing", {}).get(feature_key)
        if model_id:
            for m in global_models:
                if m.get("id") == model_id:
                    return _format_res(m, "global_routing")
            
            # If routing ID was invalid/old, try falling back to DB Default instead of ENV
            if db_default_model:
                logger.warning(f"Feature routing for {feature_key} pointed to missing ID {model_id}. Falling back to DB Default.")
                return _format_res(db_default_model, "global_default_fallback")

        # 4. Check Global Default (Tier 4)
        if db_default_model:
            return _format_res(db_default_model, "global_default")

    except Exception as e:
        logger.error(f"Error resolving LLM config for {feature_key}: {e}")
    finally:
        db.close()

    # 5. Only return ENV if absolutely no DB config was found
    return env_default
