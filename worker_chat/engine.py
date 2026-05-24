import os
import logging
import requests
from shared_core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _get_global_model_setting(key: str) -> str | None:
    """Read a model setting from the system_settings table."""
    try:
        from shared_core.database import SessionLocal
        from shared_core.models import SystemSetting
        with SessionLocal() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == "model_settings").first()
            if setting and setting.value and isinstance(setting.value, dict):
                return setting.value.get(key)
    except Exception as e:
        logger.error(f"Error reading global model settings: {e}")
    return None

def _get_model_config_from_db(model_id: str) -> dict | None:
    """Read a specific model's config from the database 'llm_models' list."""
    try:
        from shared_core.database import SessionLocal
        from shared_core.models import SystemSetting
        with SessionLocal() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == "llm_models").first()
            if setting and setting.value and isinstance(setting.value, list):
                for m in setting.value:
                    if m.get("id") == model_id or m.get("model_name") == model_id:
                        return m
    except Exception as e:
        logger.error(f"Error reading specific model config from DB: {e}")
    return None

def generate_chat_response(messages, model_id=None):
    """
    Calls the resolved LLM API (Ollama local, OpenAI, Anthropic, or OpenAI-compatible cloud)
    based on the configuration matching 'model_id' stored in the PostgreSQL database.
    """
    settings = get_settings()
    
    # Defaults
    base_url = settings.ollama.base_url
    model_name = settings.ollama.model_name
    api_key = ""
    
    # 1. Resolve configuration from Database
    if model_id:
        cfg = _get_model_config_from_db(model_id)
        if cfg:
            base_url = cfg.get("base_url", base_url)
            model_name = cfg.get("model_name", model_name)
            api_key = cfg.get("api_key", "")
            logger.info(f"Resolved DB LLM Config for ID '{model_id}': {cfg.get('name')} ({model_name})")
        else:
            logger.warning(f"Model ID '{model_id}' not found in DB. Falling back to default system settings.")
            
    # Fallbacks if still unresolved
    if not base_url:
        base_url = _get_global_model_setting("base_url") or settings.ollama.base_url
    if not model_name:
        model_name = _get_global_model_setting("model_name") or settings.ollama.model_name
        
    logger.info(f"Triggering Chat LLM completion. Endpoint: {base_url}, Model: {model_name}")
    
    # 2. Assemble payload & headers
    api_url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
        
    # If messages don't have a system prompt, insert a professional one at the start
    has_system = any(m.get("role") == "system" for m in messages)
    formatted_messages = list(messages)
    if not has_system:
        formatted_messages.insert(0, {
            "role": "system",
            "content": "Bạn là một Trợ lý AI sáng tạo chuyên nghiệp tích hợp trong hệ sinh thái VidGenius. "
                       "Nhiệm vụ của bạn là hỗ trợ người dùng viết kịch bản video marketing (unbox, review...), "
                       "biên tập tiêu đề hấp dẫn, gợi ý prompts tạo ảnh nghệ thuật bằng FLUX AI, dịch thuật Việt-Anh siêu tốc, "
                       "và đưa ra các ý tưởng dựng video sáng tạo để giữ chân người xem. Phản hồi bằng tiếng Việt ngắn gọn, chuyên nghiệp, cấu trúc rõ ràng."
        })
        
    req_payload = {
        "model": model_name,
        "messages": formatted_messages,
        "temperature": 0.7
    }
    
    # 3. Call API
    try:
        logger.info(f"Sending request to resolved chat endpoint: {api_url}")
        res = requests.post(api_url, json=req_payload, headers=headers, timeout=120)
        res.raise_for_status()
        
        res_data = res.json()
        ai_message = res_data["choices"][0]["message"]["content"]
        logger.info(f"Chat response retrieved successfully (len: {len(ai_message)})")
        return ai_message
        
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        raise Exception(f"Failed to generate response from resolved LLM: {str(e)}")
