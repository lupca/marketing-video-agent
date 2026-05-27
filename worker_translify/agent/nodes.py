import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog, AgentLog, Asset, User
from shared_core.llm_resolver import resolve_llm_config
from shared_core.constants import LLMFeature
from shared_core.minio_utils import upload_file_to_minio, is_minio_path, get_object_name
from shared_core.worker_base import insert_log, get_or_create_job_folders

from worker_translify.agent.state import TranslifyAgentState
from model.video_schema import VideoProject, Scene, SpeakerData, AudioData, VisualData, BgmData, OcrItem

logger = logging.getLogger(__name__)

# ── Robust JSON Extractor ──────────────────────────────────────────────────

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Robust helper to extract JSON from LLM response."""
    # Strip thinking block first if present
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
        
    # Try finding json block inside markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
            
    # Try finding any outer curly braces
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
            
    # Fallback to manual dictionary parsing if possible, or raise
    raise ValueError(f"Could not parse valid JSON from text: {text}")

# ── Logging Helpers ──────────────────────────────────────────────────────────

def save_node_log(
    job_id: int,
    node_name: str,
    step: str,
    input_data: Any,
    output_data: Any,
    llm_reasoning: Optional[str] = None,
    log_level: str = "INFO"
):
    """Open a separate DB session to write node log entries independently, avoiding DB transaction issues."""
    db = SessionLocal()
    try:
        def sanitize(val):
            try:
                json.dumps(val)
                return val
            except Exception:
                return str(val)

        db_log = AgentLog(
            job_id=job_id,
            step=step,
            node_name=node_name,
            input_data=sanitize(input_data),
            output_data=sanitize(output_data),
            llm_reasoning=llm_reasoning,
            log_level=log_level
        )
        db.add(db_log)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving node log for {node_name}: {e}", exc_info=True)
    finally:
        db.close()

def insert_job_log(job_id: int, message: str, level: str = "INFO"):
    """Insert log into JobLog to let user track agent updates in real-time on Web UI."""
    db = SessionLocal()
    try:
        insert_log(db, job_id, message, level)
    except Exception as e:
        logger.error(f"Error saving job log: {e}")
    finally:
        db.close()

# ── Node 1: Glossary Extractor (LLM) ──────────────────────────────────────────

def glossary_extractor_node(state: TranslifyAgentState) -> Dict[str, Any]:
    job_id = state["job_id"]
    user_id = state.get("user_id")
    logger.info(f"Node: glossary_extractor_node (job_id={job_id})")
    insert_job_log(job_id, "🔍 [Agent] Khởi động: Chiết xuất thuật ngữ (Glossary Extractor)...")
    
    project_data = state["project_data"]
    
    # Gather Chinese transcripts from all scenes
    chinese_lines = []
    for idx, scene in enumerate(project_data.scenes):
        zh = (scene.audio.zh_text or "").strip()
        if zh:
            chinese_lines.append(f"Cảnh {idx+1}: {zh}")
            
    source_content = "\n".join(chinese_lines)
    
    if not source_content:
        save_node_log(
            job_id=job_id,
            node_name="glossary_extractor",
            step="extract",
            input_data={"source_content": ""},
            output_data={"theme_summary": "", "glossary": []},
            llm_reasoning="Không có giọng nói để chiết xuất thuật ngữ."
        )
        return {
            "glossary": [],
            "theme_summary": "Video không có giọng thoại."
        }
        
    # Resolve LLM config
    config = resolve_llm_config(user_id, LLMFeature.TRANS_ANALYSIS)
    llm = ChatOpenAI(
        model=config["model_name"],
        openai_api_base=f"{config['base_url'].rstrip('/')}/v1",
        openai_api_key=config["api_key"] or "ollama",
        temperature=0.1
    )
    
    system_prompt = (
        "Bạn là chuyên gia dịch thuật video và tư vấn thuật ngữ, chuyên hiểu ngữ cảnh tiếng Trung và tối ưu hóa biểu đạt tiếng Việt.\n\n"
        "Nhiệm vụ của bạn:\n"
        "1. Tóm tắt chủ đề cốt lõi của video tiếng Trung trong đúng 2 câu tiếng Việt (theme_summary).\n"
        "2. Chiết xuất tối đa 15 thuật ngữ chuyên ngành, danh từ riêng, thương hiệu, hoặc từ khó xuất hiện trong video kèm dịch nghĩa tiếng Việt và giải thích ngắn gọn (glossary).\n\n"
        "Hãy trả về kết quả định dạng JSON thuần túy theo cấu trúc sau:\n"
        "{\n"
        '  "theme_summary": "Tóm tắt 2 câu về chủ đề video bằng tiếng Việt...",\n'
        '  "glossary": [\n'
        "    {\n"
        '      "src": "Từ tiếng Trung gốc",\n'
        '      "tgt": "Dịch nghĩa tiếng Việt đề xuất",\n'
        '      "note": "Giải thích ngắn gọn nghĩa hoặc ngữ cảnh"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Chú ý: Chỉ trả về JSON, không thêm chữ giải thích bên ngoài."
    )
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"<text>\n{source_content}\n</text>")
    ])
    
    try:
        parsed = extract_json_from_text(response.content)
        theme_summary = parsed.get("theme_summary", "Không có tóm tắt.")
        glossary = parsed.get("glossary", [])
    except Exception as e:
        logger.error(f"Failed to parse glossary extractor output: {e}")
        theme_summary = "Không thể tóm tắt do lỗi cú pháp LLM."
        glossary = []
        
    save_node_log(
        job_id=job_id,
        node_name="glossary_extractor",
        step="extract",
        input_data={"source_content": source_content},
        output_data={"theme_summary": theme_summary, "glossary": glossary},
        llm_reasoning=response.content
    )
    
    insert_job_log(job_id, f"✅ [Agent] Chiết xuất xong! Chủ đề: {theme_summary[:100]}...")
    return {
        "theme_summary": theme_summary,
        "glossary": glossary
    }

# ── Node 2: Sliding Translation (LLM) ─────────────────────────────────────────

def sliding_translation_node(state: TranslifyAgentState) -> Dict[str, Any]:
    job_id = state["job_id"]
    user_id = state.get("user_id")
    logger.info(f"Node: sliding_translation_node (job_id={job_id})")
    insert_job_log(job_id, "🔄 [Agent] Bắt đầu: Dịch thuật trượt đa ngữ cảnh (Sliding Translation)...")
    
    project_data = state["project_data"]
    glossary = state.get("glossary") or []
    theme_summary = state.get("theme_summary") or ""
    
    # Format glossary for prompt integration
    glossary_str = "\n".join([f"- {item['src']}: {item['tgt']} ({item.get('note', '')})" for item in glossary])
    if not glossary_str:
        glossary_str = "Không có thuật ngữ chuyên biệt."
        
    # Resolve LLM
    config = resolve_llm_config(user_id, LLMFeature.TRANS_ANALYSIS)
    llm = ChatOpenAI(
        model=config["model_name"],
        openai_api_base=f"{config['base_url'].rstrip('/')}/v1",
        openai_api_key=config["api_key"] or "ollama",
        temperature=0.0 # Faithfulness uses 0 temp
    )
    
    scenes = project_data.scenes
    num_scenes = len(scenes)
    
    system_prompt_template = (
        "Bạn là biên dịch viên phụ đề chuyên nghiệp, thông thạo cả tiếng Trung và tiếng Việt.\n"
        "Nhiệm vụ của bạn là dịch sát nghĩa câu thoại tiếng Trung của PHÂN CẢNH HIỆN TẠI sang tiếng Việt (Faithful Direct Translation).\n\n"
        "### Thông tin Ngữ cảnh & Chủ đề\n"
        f"Tóm tắt video: {theme_summary}\n\n"
        "### Bảng Thuật ngữ Bắt buộc Tuân thủ (Glossary):\n"
        f"{glossary_str}\n\n"
        "### Nguyên tắc Dịch thuật Sát nghĩa (Faithfulness):\n"
        "1. Dịch sát nghĩa gốc nhất có thể, truyền tải trọn vẹn ngữ nghĩa, không tùy tiện thêm thắt hay bớt chữ.\n"
        "2. Đảm bảo sử dụng chính xác các thuật ngữ trong bảng Glossary để thống nhất cách xưng hô và dịch danh từ.\n"
        "3. Dựa trên thông tin phân cảnh trước và phân cảnh sau để hiểu rõ mạch đối thoại.\n\n"
        "Hãy trả về kết quả định dạng JSON thuần túy theo cấu trúc sau:\n"
        "{\n"
        '  "direct_translation": "Câu dịch sát nghĩa tiếng Việt của phân cảnh hiện tại..."\n'
        "}\n"
        "Chú ý: Chỉ trả về duy nhất khối JSON, không giải thích gì thêm."
    )
    
    for i, scene in enumerate(scenes):
        current_zh = (scene.audio.zh_text or "").strip()
        if not current_zh:
            scene.audio.vi_text = ""
            continue
            
        # Get sliding window margins cleanly via python index scan
        prev_zh = (scenes[i-1].audio.zh_text or "").strip() if i > 0 else "Không có (Bắt đầu video)"
        next_zh = (scenes[i+1].audio.zh_text or "").strip() if i < num_scenes - 1 else "Không có (Kết thúc video)"
        
        user_content = (
            f"--- NGỮ CẢNH TRƯỢT ---\n"
            f"Phân cảnh trước (i-1) tiếng Trung: {prev_zh}\n"
            f"Phân cảnh hiện tại (i) tiếng Trung [CẦN DỊCH]: {current_zh}\n"
            f"Phân cảnh sau (i+1) tiếng Trung: {next_zh}\n\n"
            f"Hãy dịch sát nghĩa phân cảnh hiện tại (i)."
        )
        
        response = llm.invoke([
            SystemMessage(content=system_prompt_template),
            HumanMessage(content=user_content)
        ])
        
        direct_translation = current_zh # fallback
        try:
            parsed = extract_json_from_text(response.content)
            direct_translation = parsed.get("direct_translation", "").strip() or direct_translation
        except Exception as e:
            logger.error(f"Failed to parse sliding translation for scene {scene.id}: {e}")
            direct_translation = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()
            
        scene.audio.vi_text = direct_translation
        
        save_node_log(
            job_id=job_id,
            node_name="sliding_translation",
            step=f"translate_{scene.id}",
            input_data={"scene_id": scene.id, "zh_text": current_zh, "prev_zh": prev_zh, "next_zh": next_zh},
            output_data={"vi_text_direct": direct_translation},
            llm_reasoning=response.content
        )
        
        # Translate OCR screen titles mapped in this scene
        ocr_items = scene.visual.ocr_text
        if ocr_items:
            ocr_system_prompt = (
                "Bạn là biên dịch viên phụ đề chuyên nghiệp.\n"
                "Hãy dịch các cụm từ tiêu đề/chữ cứng trên màn hình dưới đây từ tiếng Trung sang tiếng Việt.\n"
                "Yêu cầu dịch cực kỳ ngắn gọn (1-4 từ), giật gân, hấp dẫn.\n\n"
                "Hãy trả về JSON dạng:\n"
                "{\n"
                '  "translations": [\n'
                '    {"zh": "từ tiếng Trung", "vi": "dịch tiếng Việt"}\n'
                '  ]\n'
                "}"
            )
            
            ocr_input = [{"zh": item.text_zh} for item in ocr_items]
            ocr_response = llm.invoke([
                SystemMessage(content=ocr_system_prompt),
                HumanMessage(content=f"Dịch danh sách chữ cứng sau:\n{json.dumps(ocr_input, ensure_ascii=False)}")
            ])
            
            try:
                ocr_parsed = extract_json_from_text(ocr_response.content)
                trans_map = {item["zh"]: item["vi"] for item in ocr_parsed.get("translations", [])}
                for item in ocr_items:
                    item.text_vi = trans_map.get(item.text_zh, item.text_zh)
            except Exception as ocr_err:
                logger.error(f"OCR translation error for scene {scene.id}: {ocr_err}")
                for item in ocr_items:
                    item.text_vi = item.text_zh
                    
            save_node_log(
                job_id=job_id,
                node_name="sliding_translation_ocr",
                step=f"translate_ocr_{scene.id}",
                input_data={"ocr_items": ocr_input},
                output_data={"ocr_translated": [itm.model_dump() for itm in ocr_items]},
                llm_reasoning=ocr_response.content
            )
            
    insert_job_log(job_id, f"✅ [Agent] Đã hoàn thành Dịch sát nghĩa cho {num_scenes} phân cảnh.")
    return {"project_data": project_data}

# ── Node 3: Reflective Adaptation (LLM) ───────────────────────────────────────

def reflective_adaptation_node(state: TranslifyAgentState) -> Dict[str, Any]:
    job_id = state["job_id"]
    user_id = state.get("user_id")
    logger.info(f"Node: reflective_adaptation_node (job_id={job_id})")
    insert_job_log(job_id, "✍️ [Agent] Bắt đầu: Biên tập và Việt hóa tự nhiên (Reflective Adaptation)...")
    
    project_data = state["project_data"]
    theme_summary = state.get("theme_summary") or ""
    glossary = state.get("glossary") or []
    config_data = state.get("config_data") or {}
    
    # Resolve campaign tone
    campaign_tone = config_data.get("campaign_tone") or config_data.get("tone") or "trẻ trung, năng động, đúng trend giới trẻ Việt Nam"
    
    glossary_str = "\n".join([f"- {item['src']}: {item['tgt']} ({item.get('note', '')})" for item in glossary])
    if not glossary_str:
        glossary_str = "Không có thuật ngữ chuyên biệt."
        
    config = resolve_llm_config(user_id, LLMFeature.TRANS_ANALYSIS)
    llm = ChatOpenAI(
        model=config["model_name"],
        openai_api_base=f"{config['base_url'].rstrip('/')}/v1",
        openai_api_key=config["api_key"] or "ollama",
        temperature=0.3 # Higher temperature for localization and adaptation
    )
    
    system_prompt = (
        "Bạn là chuyên gia Việt hóa phụ đề và tư vấn truyền thông mạng xã hội (Biên tập viên bản địa hóa).\n"
        "Nhiệm vụ của bạn là hiệu chỉnh bản dịch sát nghĩa (Direct Translation) sang văn phong Việt hóa tự nhiên (Free Translation) cuốn hút nhất.\n\n"
        "### Yêu cầu bản địa hóa:\n"
        f"1. Phong cách dịch đích hướng tới: {campaign_tone}.\n"
        "2. Đảm bảo cực kỳ trôi chảy, tự nhiên theo thói quen nói của người Việt, nhưng TUYỆT ĐỐI không làm lệch nghĩa marketing ban đầu.\n"
        "3. Giữ nguyên ranh giới thời lượng phân cảnh (không kéo dài câu dịch dài dòng lê thê hơn nghĩa gốc).\n"
        "4. Phải tuân thủ cách xưng hô nhất quán và nhất quán thuật ngữ Glossary.\n\n"
        "### Quy trình Phân tích Dịch thuật 2 bước (Line-by-line Thinking):\n"
        "Hãy suy nghĩ theo 2 bước cho phân cảnh:\n"
        "- Bước 1 (Reflection): Đánh giá độ tự nhiên, độ dài câu dịch thô thô, điểm cần tinh chỉnh.\n"
        "- Bước 2 (Free Translation): Đưa ra câu dịch Việt hóa tối ưu cuối cùng.\n\n"
        "Trả về định dạng JSON thuần túy như sau:\n"
        "{\n"
        '  "reflection": "Đánh giá ngắn gọn bản dịch sát nghĩa...",\n'
        '  "free_translation": "Câu dịch Việt hóa tự nhiên cuối cùng..."\n'
        "}\n\n"
        "Chú ý: Chỉ trả về duy nhất khối JSON."
    )
    
    for scene in project_data.scenes:
        zh_text = (scene.audio.zh_text or "").strip()
        direct_vi = (scene.audio.vi_text or "").strip()
        if not zh_text or not direct_vi:
            continue
            
        user_content = (
            f"--- THÔNG TIN PHÂN CẢNH ---\n"
            f"Câu tiếng Trung gốc: {zh_text}\n"
            f"Bản dịch sát nghĩa thô (Direct Translation): {direct_vi}\n\n"
            f"Hãy thực hiện Reflective Adaptation."
        )
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ])
        
        free_translation = direct_vi # default fallback
        reflection = ""
        try:
            parsed = extract_json_from_text(response.content)
            free_translation = parsed.get("free_translation", "").strip() or free_translation
            reflection = parsed.get("reflection", "").strip()
        except Exception as e:
            logger.error(f"Failed to parse reflective adaptation for scene {scene.id}: {e}")
            free_translation = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()
            
        scene.audio.vi_text = free_translation
        
        save_node_log(
            job_id=job_id,
            node_name="reflective_adaptation",
            step=f"reflect_{scene.id}",
            input_data={"scene_id": scene.id, "direct_vi": direct_vi},
            output_data={"vi_text_adapted": free_translation},
            llm_reasoning=f"Reflection: {reflection}\nFull response: {response.content}"
        )
        
    insert_job_log(job_id, f"✅ [Agent] Biên tập Việt hóa hoàn tất cho tất cả phân cảnh.")
    return {"project_data": project_data}

# ── Node 4: Pacing Validator (Python) ─────────────────────────────────────────

def pacing_validator_node(state: TranslifyAgentState) -> Dict[str, Any]:
    job_id = state["job_id"]
    logger.info(f"Node: pacing_validator_node (job_id={job_id})")
    
    project_data = state["project_data"]
    pacing_violations = []
    
    for scene in project_data.scenes:
        vi_text = (scene.audio.vi_text or "").strip()
        if not vi_text:
            continue
            
        duration = scene.audio.duration
        if duration <= 0:
            continue
            
        word_count = len(vi_text.split())
        max_words = max(1, int(duration * 4.0)) # maximum of 4.0 words per second
        
        if word_count > max_words:
            logger.warning(
                f"[Pacing violation] Scene {scene.id}: duration={duration:.2f}s, max_words={max_words}, actual_words={word_count} text='{vi_text}'"
            )
            pacing_violations.append(scene.id)
            
    save_node_log(
        job_id=job_id,
        node_name="pacing_validator",
        step="validate",
        input_data={"scenes_word_counts": [{"scene_id": s.id, "vi_text": s.audio.vi_text, "duration": s.audio.duration} for s in project_data.scenes if s.audio.vi_text]},
        output_data={"pacing_violations": pacing_violations},
        llm_reasoning=f"Phát hiện {len(pacing_violations)} phân cảnh bị vượt ngưỡng 4.0 từ/giây."
    )
    
    if pacing_violations:
        insert_job_log(job_id, f"⚠️ [Validation] Phát hiện {len(pacing_violations)} phân cảnh bị lỗi quá dài (tốc độ nói > 4.0 từ/s). Chuẩn bị chuyển qua sửa tự động...")
    else:
        insert_job_log(job_id, "✅ [Validation] Tất cả các phân cảnh đều khớp khít thời lượng, tốc độ nói đạt chuẩn an toàn!")
        
    return {"pacing_violations": pacing_violations}

# ── Node 5: Trimming Agent (LLM Vòng lặp) ──────────────────────────────────────

def trimming_agentic_node(state: TranslifyAgentState) -> Dict[str, Any]:
    job_id = state["job_id"]
    user_id = state.get("user_id")
    logger.info(f"Node: trimming_agentic_node (job_id={job_id})")
    
    project_data = state["project_data"]
    pacing_violations = state["pacing_violations"]
    trimming_attempts = dict(state.get("trimming_attempts") or {})
    
    config = resolve_llm_config(user_id, LLMFeature.TRANS_ANALYSIS)
    llm = ChatOpenAI(
        model=config["model_name"],
        openai_api_base=f"{config['base_url'].rstrip('/')}/v1",
        openai_api_key=config["api_key"] or "ollama",
        temperature=0.0 # High precision requires 0.0 temp
    )
    
    system_prompt = (
        "Bạn là một biên tập viên phụ đề chuyên nghiệp, chuyên tối ưu hóa độ dài câu thoại để phù hợp với thời lượng hiển thị trên màn hình trước khi thu âm.\n"
        "Nhiệm vụ của bạn là rút gọn câu thoại tiếng Việt đang bị quá dài mà KHÔNG làm thay đổi ý nghĩa cốt lõi của nó.\n\n"
        "### Quy tắc rút gọn chữ:\n"
        "1. Lược bỏ các từ đệm, từ tình thái dư thừa (ví dụ: nha, nhé, nhỉ, quả thật, thực sự, vậy thì...).\n"
        "2. Viết gọn các cụm trạng từ, tính từ bổ nghĩa không quan trọng mà không làm đổi nghĩa của động từ/danh từ chính.\n"
        "3. Sử dụng các cấu trúc ngắn gọn hơn.\n"
        "4. Tuyệt đối KHÔNG thêm bất kỳ ghi chú hay giải thích nào bên ngoài câu dịch.\n\n"
        "Hãy trả về định dạng JSON thuần túy như sau:\n"
        "{\n"
        '  "analysis": "Phân tích ngắn gọn các từ thừa có thể loại bỏ...",\n'
        '  "result": "Câu thoại tiếng Việt rút gọn cuối cùng..."\n'
        "}\n"
        "Chú ý: Chỉ trả về duy nhất khối JSON."
    )
    
    scenes_map = {s.id: s for s in project_data.scenes}
    
    for scene_id in pacing_violations:
        attempts = trimming_attempts.get(scene_id, 0)
        if attempts >= 3:
            continue
            
        trimming_attempts[scene_id] = attempts + 1
        scene = scenes_map.get(scene_id)
        if not scene:
            continue
            
        vi_text = (scene.audio.vi_text or "").strip()
        duration = scene.audio.duration
        max_words = max(1, int(duration * 4.0))
        
        insert_job_log(job_id, f"⚡ [Trimming] Đang tự động sửa cảnh {scene_id} (Lần thử {attempts+1}/3). Giới hạn từ: {max_words} (Hiện tại: {len(vi_text.split())} từ).")
        
        user_content = (
            f"--- PHÂN CẢNH CẦN RÚT GỌN ---\n"
            f"Câu thoại tiếng Việt hiện tại: '{vi_text}'\n"
            f"Thời lượng cảnh: {duration:.2f} giây\n"
            f"Số lượng từ tối đa được phép: {max_words} từ\n\n"
            f"Hãy viết lại câu thoại sao cho số lượng từ bằng hoặc ít hơn {max_words} từ."
        )
        
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ])
        
        trimmed_result = vi_text
        analysis = ""
        try:
            parsed = extract_json_from_text(response.content)
            trimmed_result = parsed.get("result", "").strip() or trimmed_result
            analysis = parsed.get("analysis", "").strip()
        except Exception as e:
            logger.error(f"Failed to parse trimmed subtitle for scene {scene_id}: {e}")
            trimmed_result = re.sub(r'<think>.*?</think>', '', response.content, flags=re.DOTALL).strip()
            
        scene.audio.vi_text = trimmed_result
        
        save_node_log(
            job_id=job_id,
            node_name="trimming_agentic",
            step=f"trim_{scene_id}_attempt_{attempts+1}",
            input_data={"scene_id": scene_id, "original_vi": vi_text, "max_words": max_words, "duration": duration},
            output_data={"trimmed_vi": trimmed_result},
            llm_reasoning=f"Analysis: {analysis}\nFull response: {response.content}"
        )
        
    return {
        "project_data": project_data,
        "trimming_attempts": trimming_attempts,
        "pacing_violations": [] # Clear to let pacing validator recheck
    }

# ── Node 6: Fallback Healing (Python Lưới đỡ) ───────────────────────────────

def fallback_healing_node(state: TranslifyAgentState) -> Dict[str, Any]:
    job_id = state["job_id"]
    logger.info(f"Node: fallback_healing_node (job_id={job_id})")
    
    project_data = state["project_data"]
    
    healed_count = 0
    for scene in project_data.scenes:
        vi_text = (scene.audio.vi_text or "").strip()
        if not vi_text:
            continue
            
        duration = scene.audio.duration
        if duration <= 0:
            continue
            
        word_count = len(vi_text.split())
        max_words = max(1, int(duration * 4.0))
        
        if word_count > max_words:
            # Physical truncation safety net
            words = vi_text.split()
            healed_text = " ".join(words[:max_words])
            logger.warning(
                f"[Fallback Healer] Truncating scene {scene.id} from {word_count} words to {max_words} words. Original: '{vi_text}' -> New: '{healed_text}'"
            )
            scene.audio.vi_text = healed_text
            healed_count += 1
            
            save_node_log(
                job_id=job_id,
                node_name="fallback_healing",
                step=f"heal_{scene.id}",
                input_data={"original_vi": vi_text, "max_words": max_words},
                output_data={"healed_vi": healed_text},
                llm_reasoning="Python Fallback Healer physically truncated word array to guarantee pacing."
            )
            
    if healed_count > 0:
        insert_job_log(job_id, f"🛡️ [Safety Net] Cắt tỉa vật lý thành công {healed_count} phân cảnh cứng đầu để bảo vệ đồng bộ hình-tiếng tuyệt đối.")
        
    return {"project_data": project_data}


