"""
Agent Runner — Orchestrates the full video creation pipeline.
Uses smolagents CodeAgent with Ollama (local LLM).

Compatible with smolagents >= 1.24.0:
  - Custom instructions go via `instructions` parameter (injected into system prompt template)
  - Step logging via `step_callbacks`
"""

import os
import json
import logging
import time
import requests
from typing import Dict, Any
from datetime import datetime, timezone

from smolagents import CodeAgent, OpenAIServerModel
from smolagents.memory import ActionStep, PlanningStep

from shared_core.database import SessionLocal
from shared_core.models import AgentSession, AgentLog
from shared_core.config import get_settings
from shared_core.llm_resolver import resolve_llm_config
from shared_core.constants import LLMFeature

from worker_agent.tools import (
    YouTubeSearchTool, DownloadVideoTool, AnalyzeVideoTool,
    YouTubeAudioSearchTool, GenerateVideoTool
)

logger = logging.getLogger(__name__)


# ── Load Prompts Dynamically ──────────────────────────────────────────────────

def load_prompt(filename: str) -> str:
    """Helper safely loading prompt templates from text files."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(current_dir, "prompts", filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt file {filename}: {e}")
        raise e


# Load prompts dynamically at startup
AGENT_INSTRUCTIONS = load_prompt("agent_instructions.txt")
AGENT_INSTRUCTIONS_RESEARCH_ONLY = load_prompt("agent_instructions_research.txt")



# ── Step Callback for DB Logging ──────────────────────────────────────────────

def _make_step_callback(session_id: str):
    """
    Factory: create a callback that persists each agent step to AgentLog table.
    This enables real-time visibility in the frontend AgentLogsDialog.
    """
    def _log_step(step):
        db = SessionLocal()
        try:
            # Determine step type and extract relevant data
            if isinstance(step, ActionStep):
                step_name = f"action_step_{step.step_number}"
                tool_name = None
                input_data = None
                output_data = None

                # Extract tool call info if present
                if step.tool_calls:
                    tc = step.tool_calls[0]  # primary tool call
                    tool_name = tc.name
                    input_data = {"arguments": tc.arguments} if tc.arguments else None

                # Capture observations (tool output / print output)
                if step.observations:
                    output_data = {"observations": step.observations[:2000]}

                llm_reasoning = None
                if step.model_output and isinstance(step.model_output, str):
                    llm_reasoning = step.model_output[:3000]

                level = "ERROR" if step.error else "INFO"

                log = AgentLog(
                    session_id=session_id,
                    step=step_name,
                    tool_name=tool_name,
                    input_data=input_data,
                    output_data=output_data,
                    llm_reasoning=llm_reasoning,
                    log_level=level,
                )
                db.add(log)
                db.commit()

            elif isinstance(step, PlanningStep):
                log = AgentLog(
                    session_id=session_id,
                    step="planning",
                    tool_name=None,
                    input_data=None,
                    output_data={"plan": step.plan[:2000]} if step.plan else None,
                    llm_reasoning=None,
                    log_level="INFO",
                )
                db.add(log)
                db.commit()

        except Exception as e:
            logger.warning(f"Failed to persist agent step log: {e}")
        finally:
            db.close()

    return _log_step


def _get_global_model_setting(key: str) -> str | None:
    """Read a model setting from the system_settings table."""
    try:
        from shared_core.database import SessionLocal as InternalSessionLocal
        from shared_core.models import SystemSetting
        with InternalSessionLocal() as db:
            setting = db.query(SystemSetting).filter(SystemSetting.key == "model_settings").first()
            if setting and setting.value and isinstance(setting.value, dict):
                return setting.value.get(key)
    except Exception:
        pass
    return None


# ── Agent Factory ─────────────────────────────────────────────────────────────

def create_agent(session_id: str = None, user_id: str = None, mode: str = "full",
                 base_url: str = None, model_name: str = None):
    """
    Create a CodeAgent configured for local Ollama LLM.
    
    Priority: 
    1. Per-session override (passed as arguments)
    2. Hierarchical Resolver (User Preferences -> Global Routing -> Defaults)
    """
    # 1. Resolve configuration (hierarchical fallback)
    config = resolve_llm_config(user_id, LLMFeature.VIDEO_ORCHESTRATOR)
    
    effective_base_url = base_url or config["base_url"]
    effective_model = model_name or config["model_name"]
    api_key = config["api_key"] or "ollama"
    
    logger.info(f"Setting up Agent Orchestrator with model {effective_model} from {config['source']} at {effective_base_url}")

    # Configure Ollama or OpenAI compatible endpoint
    model = OpenAIServerModel(
        model_id=effective_model,
        api_base=f"{effective_base_url.rstrip('/')}/v1",
        api_key=api_key,
    )
    
    # Build step callbacks dict to register for multiple step types
    callbacks = {}
    if session_id:
        cb = _make_step_callback(session_id)
        callbacks = {
            ActionStep: [cb],
            PlanningStep: [cb],
        }

    if mode == "research_only":
        agent_instructions = AGENT_INSTRUCTIONS_RESEARCH_ONLY
        tools = [
            YouTubeSearchTool(),
            DownloadVideoTool(),
            AnalyzeVideoTool(),
            YouTubeAudioSearchTool(),
        ]
    else:
        agent_instructions = AGENT_INSTRUCTIONS
        tools = [
            YouTubeSearchTool(),
            DownloadVideoTool(),
            AnalyzeVideoTool(),
            YouTubeAudioSearchTool(),
            GenerateVideoTool(),
        ]
    
    return CodeAgent(
        tools=tools,
        model=model,
        instructions=agent_instructions,
        max_steps=15,
        step_callbacks=callbacks if callbacks else None,
    )


# ── Session Executor ──────────────────────────────────────────────────────────

def run_agent_session_impl(session_id: str):
    """Execute the agent process, log interactions via step callbacks, and update DB."""
    db = SessionLocal()
    session = db.query(AgentSession).filter(AgentSession.id == session_id).first()
    if not session:
        logger.error(f"AgentSession {session_id} not found.")
        db.close()
        return

    # Guard: don't re-process sessions that are already RUNNING/COMPLETED
    if session.status not in ("PENDING", "FAILED"):
        logger.warning(f"AgentSession {session_id} status is {session.status}, skipping.")
        db.close()
        return

    try:
        session.status = "RUNNING"
        db.commit()

        mode = "full"
        model_settings = {}
        if session.config and isinstance(session.config, dict):
            mode = session.config.get("mode", "full")
            model_settings = session.config.get("model_settings", {})

        agent = create_agent(
            session_id=session_id, 
            user_id=session.user_id,
            mode=mode,
            base_url=model_settings.get("base_url"),
            model_name=model_settings.get("model_name"),
        )
        
        # Build prompt
        if mode == "research_only":
            task_prompt = (
                f"Vui lòng thực hiện tìm kiếm và tải về {session.video_count} video dựa trên từ khóa: '{session.keyword}'.\n"
                f"User ID của người dùng là: '{session.user_id}'. Hãy truyền tham số này cho các tool cần thiết.\n"
            )
        else:
            task_prompt = (
                f"Vui lòng thực hiện tạo {session.video_count} video dựa trên từ khóa: '{session.keyword}'.\n"
                f"User ID của người dùng là: '{session.user_id}'. Hãy truyền tham số này cho tool generate_video."
            )

        logger.info(f"Starting agent for session {session_id}")
        
        # Execute agent
        result = agent.run(task_prompt)
        
        # Update session
        session.status = "COMPLETED"
        session.summary = str(result)[:5000]  # cap summary length
        session.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.error(f"Agent error for session {session_id}: {e}", exc_info=True)
        session.status = "FAILED"
        session.summary = str(e)[:2000]
        session.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _extract_sentences_from_script(script_content: str, title: str) -> list:
    """Helper to extract meaningful sentences from script content for draft backups."""
    sentences = []
    if script_content:
        # Tách câu đơn giản bằng dấu chấm, chấm hỏi, chấm than hoặc xuống dòng
        raw_parts = []
        for line in script_content.split("\n"):
            for part in line.split("."):
                part = part.strip()
                if part:
                    raw_parts.append(part)
        sentences = [s for s in raw_parts if len(s) > 5]  # chỉ lấy câu có nghĩa

    if not sentences:
        sentences = [
            title or "Giới thiệu sản phẩm ấn tượng",
            "Khám phá tính năng nổi bật vượt trội",
            "Mua ngay hôm nay để nhận ưu đãi!"
        ]
    return sentences


def _heal_review(draft_params: dict, sentences: list) -> dict:
    """Logic sửa lỗi phòng thủ cho worker review."""
    # Đảm bảo assets và cấu trúc tối thiểu
    if "assets" not in draft_params or not isinstance(draft_params["assets"], dict):
        draft_params["assets"] = {}
    assets = draft_params["assets"]
    
    if "audio" not in assets or not isinstance(assets["audio"], dict):
        assets["audio"] = {}
    if "bgm_path" not in assets["audio"] or not assets["audio"]["bgm_path"]:
        assets["audio"]["bgm_path"] = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
        
    if "video_folders" not in assets or not isinstance(assets["video_folders"], dict):
        assets["video_folders"] = {
            "1": "https://assets.mixkit.co/videos/preview/mixkit-holding-a-smartphone-with-a-green-screen-41775-large.mp4"
        }

    # Sửa lỗi phổ biến: LLM tự chế 'review_points' hoặc 'points' thay vì 'timeline_script'
    review_points = []
    if "review_points" in draft_params and isinstance(draft_params["review_points"], list):
        review_points = draft_params["review_points"]
    elif "points" in draft_params and isinstance(draft_params["points"], list):
        review_points = draft_params["points"]
        
    if ("timeline_script" not in draft_params or not isinstance(draft_params["timeline_script"], list)) and review_points:
        # Tự động convert review_points thành timeline_script!
        timeline_script = []
        for idx, pt in enumerate(review_points):
            timeline_script.append({
                "segment": f"0{idx+1}_point" if idx < 9 else f"{idx+1}_point",
                "video_source": "1",  # map tới key video_folders
                "time_range": [idx * 5, (idx + 1) * 5],
                "text_overlay": pt,
                "highlight_words": pt.split()[:2] if len(pt.split()) >= 2 else [pt],
                "visual_effects": ["camera_shake"] if idx == 0 else [],
                "pacing": {
                    "min_clip_duration": 0.8,
                    "max_clip_duration": 1.5
                }
            })
        draft_params["timeline_script"] = timeline_script

    # Nếu vẫn không có timeline_script, tự động tách kịch bản thô thành các segment!
    if "timeline_script" not in draft_params or not isinstance(draft_params["timeline_script"], list) or len(draft_params["timeline_script"]) == 0:
        timeline_script = []
        for idx, sen in enumerate(sentences[:5]):  # Giới hạn tối đa 5 segments cho nháp
            segment_name = "01_hook" if idx == 0 else (f"0{idx+1}_body" if idx < len(sentences[:5]) - 1 else f"0{idx+1}_outro")
            timeline_script.append({
                "segment": segment_name,
                "video_source": "1",
                "time_range": [idx * 6, (idx + 1) * 6],
                "text_overlay": sen,
                "highlight_words": sen.split()[:2] if len(sen.split()) >= 2 else [sen],
                "visual_effects": ["camera_shake"] if idx == 0 else [],
                "pacing": {
                    "min_clip_duration": 0.8,
                    "max_clip_duration": 1.5
                }
            })
        draft_params["timeline_script"] = timeline_script

    # Đảm bảo các segment trong timeline_script có đầy đủ các trường bắt buộc
    for idx, seg in enumerate(draft_params["timeline_script"]):
        if not isinstance(seg, dict):
            continue
        if "segment" not in seg:
            seg["segment"] = f"segment_{idx+1}"
        if "video_source" not in seg:
            seg["video_source"] = "1"
        if "time_range" not in seg:
            seg["time_range"] = [idx * 5, (idx + 1) * 5]
        if "text_overlay" not in seg:
            seg["text_overlay"] = sentences[idx % len(sentences)]
        if "highlight_words" not in seg:
            words = seg["text_overlay"].split()
            seg["highlight_words"] = words[:2] if len(words) >= 2 else words
        if "visual_effects" not in seg:
            seg["visual_effects"] = []
        if "pacing" not in seg:
            seg["pacing"] = {"min_clip_duration": 0.8, "max_clip_duration": 1.5}

    # Dọn dẹp trường review_points cũ để tránh rác dữ liệu
    draft_params.pop("review_points", None)
    draft_params.pop("points", None)
    return draft_params


def _heal_slideshow(draft_params: dict, sentences: list, title: str) -> dict:
    """Logic sửa lỗi phòng thủ cho worker slideshow."""
    if "input_json" not in draft_params or not isinstance(draft_params["input_json"], dict):
        draft_params["input_json"] = {}
    input_json = draft_params["input_json"]

    # Nếu LLM sinh ra products ở root thay vì trong input_json, hãy di chuyển nó vào trong
    if "products" in draft_params and "products" not in input_json:
        input_json["products"] = draft_params.pop("products")

    if "intro_text" not in input_json or not input_json["intro_text"]:
        input_json["intro_text"] = title or "Chào mừng đến với " + (sentences[0][:20] if sentences else "Video")
    if "outro_text" not in input_json or not input_json["outro_text"]:
        input_json["outro_text"] = "Mua ngay tại giỏ hàng bên dưới!"

    if "products" not in input_json or not isinstance(input_json["products"], list) or len(input_json["products"]) == 0:
        products = []
        # Tự sinh slideshow products dựa trên kịch bản thô
        for idx, sen in enumerate(sentences[:4]):
            products.append({
                "image": f"https://images.unsplash.com/photo-{1523275335684 + idx * 1000}-37898b6baf30?w=500",
                "text": sen,
                "hook": f"Đặc điểm {idx+1}"
            })
        input_json["products"] = products

    # Đảm bảo mỗi sản phẩm có đầy đủ image, text, hook
    for idx, prod in enumerate(input_json["products"]):
        if not isinstance(prod, dict):
            continue
        if "image" not in prod or not prod["image"]:
            prod["image"] = f"https://images.unsplash.com/photo-{1523275335684 + idx * 100}-37898b6baf30?w=500"
        if "text" not in prod or not prod["text"]:
            prod["text"] = sentences[idx % len(sentences)]
        if "hook" not in prod or not prod["hook"]:
            prod["hook"] = "Khám phá ngay"
    return draft_params


def _heal_unbox_viral(draft_params: dict, sentences: list) -> dict:
    """Logic sửa lỗi phòng thủ cho worker unbox_viral."""
    if "clips" not in draft_params or not isinstance(draft_params["clips"], list) or len(draft_params["clips"]) == 0:
        draft_params["clips"] = ["https://assets.mixkit.co/videos/preview/mixkit-unpacking-a-gift-box-41584-large.mp4"]
    if "audio" not in draft_params or not draft_params["audio"]:
        draft_params["audio"] = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"
        
    if "text_events" not in draft_params or not isinstance(draft_params["text_events"], list) or len(draft_params["text_events"]) == 0:
        text_events = []
        for idx, sen in enumerate(sentences[:3]):
            text_events.append({
                "time": float(idx * 3.5),
                "text": sen,
                "effect": "hook" if idx == 0 else "feature"
            })
        draft_params["text_events"] = text_events
        
    # Đảm bảo từng text_event có time, text, effect
    for idx, ev in enumerate(draft_params["text_events"]):
        if not isinstance(ev, dict):
            continue
        if "time" not in ev:
            ev["time"] = float(idx * 3.0)
        if "text" not in ev:
            ev["text"] = sentences[idx % len(sentences)]
        if "effect" not in ev:
            ev["effect"] = "hook" if idx == 0 else "feature"
    return draft_params


def _heal_translify(draft_params: dict) -> dict:
    """Logic sửa lỗi phòng thủ cho worker translify."""
    if "video" not in draft_params or not draft_params["video"]:
        draft_params["video"] = "https://assets.mixkit.co/videos/preview/mixkit-holding-a-smartphone-with-a-green-screen-41775-large.mp4"
    if "voice_name" not in draft_params or not draft_params["voice_name"]:
        draft_params["voice_name"] = "vi-VN-NamMinhNeural"
    return draft_params


HEALERS_REGISTRY = {
    "review": _heal_review,
    "slideshow": _heal_slideshow,
    "unbox_viral": _heal_unbox_viral,
    "translify": _heal_translify
}


def heal_draft_parameters(worker_type: str, draft_params: Dict[str, Any], script_content: str, title: str) -> Dict[str, Any]:
    """
    Hậu xử lý và chuẩn hóa draft_parameters để đảm bảo tính toàn vẹn dữ liệu 100%.
    Nếu LLM bị lỗi hoặc sinh thiếu trường/sai định dạng, hàm này sẽ tự động sửa lỗi
    và map kịch bản thô vào cấu trúc chuẩn để React UI không bao giờ hiển thị form trống.
    """
    if not isinstance(draft_params, dict):
        draft_params = {}

    sentences = _extract_sentences_from_script(script_content, title)
    
    healer = HEALERS_REGISTRY.get(worker_type)
    if healer:
        if worker_type == "slideshow":
            return healer(draft_params, sentences, title)
        elif worker_type in ("review", "unbox_viral"):
            return healer(draft_params, sentences)
        else:
            return healer(draft_params)
            
    return draft_params



def call_ollama_with_retry(api_url: str, req_payload: dict, headers: dict, retries: int = 3, backoff: float = 2.0) -> dict:
    """Thực hiện gọi API Ollama kèm cơ chế Exponential Backoff."""
    last_error = None
    for attempt in range(retries):
        try:
            res = requests.post(api_url, json=req_payload, headers=headers, timeout=60)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            last_error = e
            wait_time = backoff * (2 ** attempt)
            logger.warning(f"Ollama call failed (Attempt {attempt+1}/{retries}). Retrying in {wait_time}s... Error: {e}")
            time.sleep(wait_time)
    raise RuntimeError(f"Ollama API unavailable after {retries} retries. Last error: {last_error}")


def process_tmcp_webhook_impl(job_id: int):
    """
    Leader Agent: Phân tích kịch bản từ TMCP, dùng LLM xác định worker phù hợp
    và tạo một Job mới ở trạng thái DRAFT.
    """
    import json
    import requests
    from datetime import datetime, timezone
    from shared_core.database import SessionLocal
    from shared_core.models import VideoJob, JobLog
    from shared_core.config import get_settings

    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.error(f"Job webhook {job_id} not found in database.")
        db.close()
        return

    try:
        logger.info(f"Leader Agent starting analysis for job: {job_id}")
        job.status = "PROCESSING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # 1. Trích xuất payload từ config_data
        payload = job.config_data
        if not payload:
            raise ValueError("No payload found in config_data")
        
        if isinstance(payload, str):
            payload = json.loads(payload)

        # 2. Xây dựng thông tin gửi cho LLM
        brand = payload.get("brand_context", {})
        campaign = payload.get("campaign_context", {})
        variant = payload.get("variant_data", {})
        
        brand_name = brand.get("brand_name", "")
        tone = brand.get("tone_of_voice", "")
        colors = brand.get("brand_colors", [])
        
        campaign_name = campaign.get("campaign_name", "")
        audience = campaign.get("target_audience", "")
        objective = campaign.get("objective", "")
        
        title = variant.get("title", "")
        script_content = variant.get("script_content", "")
        hints = variant.get("media_hints", [])
        duration = variant.get("suggested_duration", 15)

        # 3. Gọi LLM Ollama
        settings = get_settings()
        base_url = _get_global_model_setting("base_url") or settings.ollama.base_url
        model_name = _get_global_model_setting("model_name") or settings.ollama.model_name
        
        system_prompt = load_prompt("leader_system_prompt.txt")

        user_content = (
            f"Thông tin từ TMCP:\n"
            f"- Thương hiệu: {brand_name}\n"
            f"- Tone giọng: {tone}\n"
            f"- Màu sắc: {colors}\n"
            f"- Chiến dịch: {campaign_name}\n"
            f"- Đối tượng: {audience}\n"
            f"- Mục tiêu: {objective}\n"
            f"- Tiêu đề Kịch bản: {title}\n"
            f"- Nội dung Kịch bản: {script_content}\n"
            f"- Gợi ý phân cảnh: {hints}\n"
            f"- Thời lượng gợi ý: {duration} giây\n\n"
            f"Hãy suy nghĩ kỹ, chọn worker thích hợp nhất và xuất JSON."
        )

        logger.info(f"Calling Ollama at {base_url} with model {model_name}")
        api_url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        req_payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "response_format": {"type": "json_object"}
        }

        # Gọi Ollama với cơ chế tự phục hồi lỗi mạng (Exponential Backoff)
        res_data = call_ollama_with_retry(api_url, req_payload, headers)
        
        ai_message = res_data["choices"][0]["message"]["content"]
        logger.info(f"Ollama response: {ai_message}")

        # Parse AI response
        parsed_res = json.loads(ai_message)
        reasoning = parsed_res.get("reasoning", "No reasoning provided")
        worker_type = parsed_res.get("worker_type", "slideshow")
        draft_params = parsed_res.get("draft_parameters", {})

        # Hợp thức hóa worker_type
        valid_workers = ["slideshow", "review", "unbox_viral", "translify"]
        if worker_type not in valid_workers:
            logger.warning(f"Invalid worker_type '{worker_type}' returned, defaulting to 'slideshow'")
            worker_type = "slideshow"

        # Hậu xử lý phòng thủ để đảm bảo tính toàn vẹn 100% của draft_parameters trước khi ghi vào DB
        logger.info(f"Applying defensive healing to draft parameters for worker: {worker_type}")
        draft_params = heal_draft_parameters(worker_type, draft_params, script_content, title)

        # Preserve original TMCP context in config_data.metadata.tmcp_context
        if "metadata" not in draft_params or not isinstance(draft_params["metadata"], dict):
            draft_params["metadata"] = {}
        draft_params["metadata"]["tmcp_context"] = payload

        # 4. Tạo Job mới ở trạng thái DRAFT
        new_job = VideoJob(
            job_type=worker_type,
            project_id=job.project_id,
            status="DRAFT",
            priority=0,
            config_data=draft_params,
            draft_parameters=draft_params,
            progress_percent=0,
            note=f"Draft generated by Leader Agent for Variant: {payload.get('source_id')}",
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        logger.info(f"Created DRAFT job {new_job.id} for worker {worker_type}")

        # 5. Ghi log phân tích vào Job chính
        db_log = JobLog(
            job_id=job.id,
            log_level="INFO",
            message=f"Leader Agent reasoning:\n{reasoning}\nSelected worker: {worker_type}. Created Draft Job ID: {new_job.id}"
        )
        db.add(db_log)

        # 6. Đánh dấu Job chính là COMPLETED
        job.status = "COMPLETED"
        job.progress_percent = 100
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Leader Agent task completed successfully for job: {job_id}")

    except Exception as e:
        logger.error(f"Error in process_tmcp_webhook_impl: {str(e)}", exc_info=True)
        job.status = "FAILED"
        job.error_message = f"Leader Agent Error: {str(e)}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Thêm log lỗi vào JobLog
        try:
            db_log = JobLog(
                job_id=job.id,
                log_level="ERROR",
                message=f"Leader Agent failed: {str(e)}"
            )
            db.add(db_log)
            db.commit()
        except Exception as log_ex:
            logger.error(f"Failed to log error to DB: {log_ex}")

    finally:
        db.close()
