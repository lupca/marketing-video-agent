import os
import logging
import requests
from shared_core.config import get_settings
from shared_core.llm_resolver import resolve_llm_config
from shared_core.constants import LLMFeature

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_chat_response(messages, user_id=None, model_id=None):
    """
    Calls the resolved LLM API (Ollama local, OpenAI, Anthropic, or OpenAI-compatible cloud)
    based on the configuration resolved from User/Global settings.
    """
    # 1. Resolve configuration (hierarchical fallback)
    # We ignore model_id if it's not provided by the user explicitly, 
    # but the resolver handles the logic of which model to use.
    # If the user passed a specific model_id via UI (override), we could pass it to resolver 
    # our architecture prefers routing by feature_key.

    config = resolve_llm_config(user_id, LLMFeature.CHAT_ASSISTANT)

    base_url = config["base_url"]

    model_name = config["model_name"]
    api_key = config["api_key"]
    
    logger.info(f"Triggering Chat LLM completion. Source: {config['source']}, Endpoint: {base_url}, Model: {model_name}")
    
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
