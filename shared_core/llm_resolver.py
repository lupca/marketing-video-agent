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
    """
    settings = get_settings()
    db = SessionLocal()
    
    # 0. Start with hardcoded defaults from config.py
    resolved = {
        "base_url": settings.ollama.base_url,
        "model_name": settings.ollama.model_name,
        "api_key": "",
        "provider": "ollama",
        "source": "environment_default"
    }

    try:
        # 1. Fetch Global Settings (needed for most steps)
        global_models_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm_models").first()
        global_routing_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm_routing").first()
        
        global_models = global_models_setting.value if global_models_setting and global_models_setting.value else []
        global_routing = global_routing_setting.value if global_routing_setting and global_routing_setting.value else {}

        # 2. Check User-Level Preferences (Tier 1 & 2)
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.llm_preferences:
                user_prefs = user.llm_preferences
                user_routing = user_prefs.get("routing", {})
                model_id = user_routing.get(feature_key)
                
                if model_id:
                    # Check in User's Custom Models
                    custom_models = user_prefs.get("custom_models", [])
                    for m in custom_models:
                        if m.get("id") == model_id:
                            logger.info(f"Resolved User-Custom LLM for {feature_key} (user={user_id})")
                            return {
                                "base_url": m.get("base_url"),
                                "model_name": m.get("model_name"),
                                "api_key": m.get("api_key", ""),
                                "provider": m.get("provider", "openai"),
                                "source": "user_custom"
                            }
                    
                    # Check in Global Models (User selected a system model)
                    for m in global_models:
                        if m.get("id") == model_id:
                            logger.info(f"Resolved User-selected Global LLM for {feature_key} (user={user_id})")
                            return {
                                "base_url": m.get("base_url"),
                                "model_name": m.get("model_name"),
                                "api_key": m.get("api_key", ""),
                                "provider": m.get("provider", "ollama"),
                                "source": "user_selected_global"
                            }

        # 3. Check Global Feature Routing (Tier 3)
        model_id = global_routing.get(feature_key)
        if model_id:
            for m in global_models:
                if m.get("id") == model_id:
                    logger.info(f"Resolved Global-Route LLM for {feature_key}")
                    return {
                        "base_url": m.get("base_url"),
                        "model_name": m.get("model_name"),
                        "api_key": m.get("api_key", ""),
                        "provider": m.get("provider", "ollama"),
                        "source": "global_routing"
                    }

        # 4. Check Global Default (Tier 4)
        default_id = global_routing.get("default")
        if default_id:
            for m in global_models:
                if m.get("id") == default_id:
                    logger.info(f"Resolved Global-Default LLM for {feature_key}")
                    return {
                        "base_url": m.get("base_url"),
                        "model_name": m.get("model_name"),
                        "api_key": m.get("api_key", ""),
                        "provider": m.get("provider", "ollama"),
                        "source": "global_default"
                    }

    except Exception as e:
        logger.error(f"Error resolving LLM config for {feature_key}: {e}", exc_info=True)
    finally:
        db.close()

    # 5. Return fallback (Tier 5)
    logger.info(f"Using Environment-Default LLM for {feature_key}")
    return resolved
