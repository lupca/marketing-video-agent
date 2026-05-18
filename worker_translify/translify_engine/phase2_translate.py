import os
import re
import json
import logging
import httpx
from shared_core.config import get_settings

logger = logging.getLogger(__name__)

def translate_with_ollama(texts: list[str], prompt_type: str = "subtitle") -> list[str]:
    """
    Send a batch of Chinese texts to Ollama to translate into young, dynamic Vietnamese.
    Retains line count precisely.
    """
    if not texts:
        return []
        
    cfg = get_settings().ollama
    # Default to localhost if URL is empty or matches default
    base_url = cfg.base_url or "http://localhost:11434"
    # Ensure URL ends with /v1 or correct ollama endpoints
    ollama_api = f"{base_url}/api/chat"
    
    # We default to qwen2.5:7b as requested by user
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    
    system_prompt = (
        "Bạn là một biên dịch viên chuyên nghiệp cho video ngắn Douyin/TikTok. "
        "Hãy dịch câu tiếng Trung sau sang tiếng Việt.\n"
        "Yêu cầu:\n"
        "1. Dịch câu tiếng Trung đầu vào thành câu tiếng Việt tương ứng trẻ trung, tự nhiên, đúng trend giới trẻ Việt Nam.\n"
        "2. Chỉ trả về duy nhất câu tiếng Việt đã dịch. TUYỆT ĐỐI không trả về bất kỳ chữ Trung Quốc nào, không có chữ Hán, không thêm ghi chú hay giải thích nào khác."
    )
    
    if prompt_type == "ocr":
        system_prompt = (
            "Bạn là biên dịch viên video ngắn. Hãy dịch chữ cứng tiêu đề màn hình sau từ tiếng Trung sang tiếng Việt.\n"
            "Yêu cầu:\n"
            "1. Dịch thật ngắn gọn (1-4 từ), giật gân, hấp dẫn.\n"
            "2. Chỉ trả về duy nhất câu tiếng Việt đã dịch, KHÔNG chứa bất kỳ chữ Trung Quốc hay chữ Hán nào."
        )

    # Format batch input
    user_content = "\n".join(texts)
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_predict": 128
        },
        "stream": False
    }
    
    logger.info(f"Connecting to Ollama at {ollama_api} using model {model_name}...")
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(ollama_api, json=payload)
            if resp.status_code != 200:
                logger.error(f"Ollama API error {resp.status_code}: {resp.text}")
                return [f"[Dịch lỗi]" for _ in texts]
                
            data = resp.json()
            translated_content = data["message"]["content"].strip()
            # Strip deepseek/qwen thinking blocks if present
            translated_content = re.sub(r'<think>.*?</think>', '', translated_content, flags=re.DOTALL).strip()
            
            # Remove Chinese characters and outer quotes/brackets
            translated_content = re.sub(r'[\u4e00-\u9fff]', '', translated_content)
            translated_content = translated_content.strip('"\'「」[]{}')
            
            # Split lines and align
            lines = [line.strip() for line in translated_content.split("\n") if line.strip()]
            
            # Post-processing to match length
            if len(lines) != len(texts):
                logger.warning(f"Ollama line count mismatch: Input={len(texts)}, Output={len(lines)}. Aligning...")
                if len(lines) < len(texts):
                    lines.extend([""] * (len(texts) - len(lines)))
                else:
                    lines = lines[:len(texts)]
                    
            return lines
    except Exception as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        # Fallback simple translation simulation / raw output placeholder
        # Strip Chinese and return a clean fallback label
        clean_fallback = [re.sub(r'[\u4e00-\u9fff]', '', t).strip() for t in texts]
        return [f"[Dịch] {cf}" if cf else "[Âm thanh]" for cf in clean_fallback]

def translate_pipeline_data(whisper_segments: list[dict], ocr_results: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Coordinate translation for Whisper segments and OCR detections.
    """
    # 1. Translate Whisper vocal segments
    if whisper_segments:
        logger.info(f"Translating {len(whisper_segments)} vocal subtitle segments...")
        chinese_texts = [seg["text"] for seg in whisper_segments]
        
        # Translate line-by-line (batch_size = 1) for 100% alignment guarantee on smaller models
        batch_size = 1
        translated_texts = []
        for i in range(0, len(chinese_texts), batch_size):
            batch = chinese_texts[i:i+batch_size]
            translated_batch = translate_with_ollama(batch, prompt_type="subtitle")
            translated_texts.extend(translated_batch)
            
        for seg, vi_text in zip(whisper_segments, translated_texts):
            seg["original_text"] = seg["text"]
            seg["text"] = vi_text
            
    # 2. Translate OCR screen titles
    if ocr_results:
        logger.info(f"Translating {len(ocr_results)} on-screen OCR text boxes...")
        ocr_texts = [res["text"] for res in ocr_results]
        
        # Translate line-by-line (batch_size = 1) for 100% alignment guarantee on smaller models
        batch_size = 1
        translated_ocr = []
        for i in range(0, len(ocr_texts), batch_size):
            batch = ocr_texts[i:i+batch_size]
            translated_batch = translate_with_ollama(batch, prompt_type="ocr")
            translated_ocr.extend(translated_batch)
            
        for res, vi_text in zip(ocr_results, translated_ocr):
            res["original_text"] = res["text"]
            res["text"] = vi_text
            
    return whisper_segments, ocr_results
