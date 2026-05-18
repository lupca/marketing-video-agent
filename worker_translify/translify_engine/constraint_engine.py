import os
import re
import logging
import httpx
from shared_core.config import get_settings
from model.video_schema import VideoProject

logger = logging.getLogger(__name__)

def rewrite_with_ollama(original_text: str, duration: float, max_words: int) -> str:
    """
    Call Ollama to rewrite a Vietnamese sentence to fit a specific duration constraint.
    """
    cfg = get_settings().ollama
    base_url = cfg.base_url or "http://localhost:11434"
    ollama_api = f"{base_url}/api/chat"
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    system_prompt = (
        "Bạn là một biên dịch viên video ngắn chuyên nghiệp.\n"
        "Yêu cầu:\n"
        f"1. Hãy viết lại câu tiếng Việt dưới đây sao cho cực kỳ ngắn gọn, TỐI ĐA {max_words} từ/âm tiết, nhưng phải giữ nguyên ý nghĩa marketing cốt lõi và phong cách tự nhiên, hấp dẫn.\n"
        "2. Chỉ trả về duy nhất câu tiếng Việt mới đã rút gọn, TUYỆT ĐỐI không thêm giải thích, không có chữ Hán, không thêm ghi chú nào khác."
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": original_text}
        ],
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 64
        },
        "stream": False
    }

    logger.info(f"Ollama Rewrite: '{original_text}' (limit: {max_words} words, dur: {duration}s)...")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(ollama_api, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                rewritten = data["message"]["content"].strip()
                # Strip deepseek/qwen thinking blocks if present
                rewritten = re.sub(r'<think>.*?</think>', '', rewritten, flags=re.DOTALL).strip()
                # Clean up punctuation and Chinese characters
                rewritten = re.sub(r'[\u4e00-\u9fff]', '', rewritten)
                rewritten = rewritten.strip('"\'「」[]{}')
                logger.info(f"Ollama Rewrite Result: '{rewritten}'")
                return rewritten
            else:
                logger.error(f"Ollama Rewrite API error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Failed to call Ollama for rewrite: {e}")

    # Fallback: simple truncation of words
    words = original_text.split()
    fallback = " ".join(words[:max_words])
    logger.warning(f"Ollama Rewrite fallback: '{fallback}'")
    return fallback

class ConstraintEngine:
    def __init__(self, speed_threshold: float = 4.0):
        """
        speed_threshold: Maximum syllables/words per second allowed for natural speech.
        """
        self.speed_threshold = speed_threshold

    def apply_constraints(self, project: VideoProject, work_dir: str = None) -> VideoProject:
        """
        Scan all scenes in the project. If the Vietnamese transcript is too long for the scene's duration,
        rewrite it using Ollama to fit the time limit.
        """
        logger.info("=== Starting Constraint-Aware Rewrite Engine ===")
        
        modified_count = 0
        for scene in project.scenes:
            vi_text = scene.audio.vi_text
            if not vi_text:
                continue

            vi_text_clean = vi_text.strip()
            if not vi_text_clean:
                continue

            duration = scene.audio.duration
            if duration <= 0:
                continue

            # Word count
            word_count = len(vi_text_clean.split())
            max_words = max(1, int(duration * self.speed_threshold))

            if word_count > max_words:
                logger.warning(
                    f"[{scene.id}] Duration Violation! Duration: {duration:.2f}s, Max Words: {max_words}, "
                    f"Current Words: {word_count}. Text: '{vi_text_clean}'"
                )
                # Trigger rewrite
                rewritten_text = rewrite_with_ollama(vi_text_clean, duration, max_words)
                scene.audio.vi_text = rewritten_text
                modified_count += 1
            else:
                logger.info(
                    f"[{scene.id}] Duration Constraint OK. Duration: {duration:.2f}s, Max Words: {max_words}, "
                    f"Current Words: {word_count}. Text: '{vi_text_clean}'"
                )

        logger.info(f"=== Constraint-Aware Rewrite Complete. Modified {modified_count} scenes ===")
        
        # Save updated project JSON DB if work_dir is provided
        if work_dir:
            json_path = os.path.join(work_dir, "project_db.json")
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(project.model_dump_json(indent=2))
            logger.info(f"Saved updated VideoProject JSON DB to: {json_path}")

        return project
