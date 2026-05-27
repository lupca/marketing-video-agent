"""
Leader Graph Nodes — Encapsulates all LangGraph node functions for script analysis.
"""

import json
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog, AgentLog
from shared_core.llm_resolver import resolve_llm_config
from shared_core.constants import LLMFeature

from worker_leader.state import LeaderAgentState
from worker_leader.tools import validate_video_pacing
from worker_leader.healers import heal_draft_parameters
from worker_leader.healers.dispatcher import VALID_WORKER_TYPES
from worker_leader.utils import extract_json_from_text, load_prompt

logger = logging.getLogger(__name__)

# ── Logging Helper ───────────────────────────────────────────────────────────

def save_node_log(
    job_id: int,
    node_name: str,
    step: str,
    input_data: Any,
    output_data: Any,
    llm_reasoning: Optional[str] = None,
    log_level: str = "INFO"
):
    """Mở DB session độc lập, lưu log ghi vết của Node rồi đóng ngay lập tức để tránh tranh chấp DB."""
    db = SessionLocal()
    try:
        def sanitize(val):
            try:
                import json
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

# ── Nodes ───────────────────────────────────────────────────────────────────

def extract_context_node(state: LeaderAgentState) -> Dict[str, Any]:
    """Extract and normalize context from raw payload."""
    from worker_leader.leader_runner import _extract_payload_context
    logger.info(f"Node: extract_context_node (job_id={state.get('job_id')})")
    
    payload = state["raw_payload"]
    ctx = _extract_payload_context(payload)
    
    save_node_log(
        job_id=state["job_id"],
        node_name="extract",
        step="analyze",
        input_data=payload,
        output_data=ctx,
        llm_reasoning="Trích xuất bối cảnh kịch bản và thương hiệu từ payload TMCP."
    )
    
    return {
        "context": ctx,
        "attempts": 0,
        "pacing_errors": []
    }

def routing_node(state: LeaderAgentState) -> Dict[str, Any]:
    """LLM node to decide the worker_type."""
    logger.info("Node: routing_node")
    ctx = state["context"]
    user_id = state["user_id"]
    
    # Resolve LLM config
    config = resolve_llm_config(user_id, LLMFeature.LEADER_ANALYSIS)
    llm = ChatOpenAI(
        model=config["model_name"],
        openai_api_base=f"{config['base_url'].rstrip('/')}/v1",
        openai_api_key=config["api_key"] or "ollama",
        temperature=0
    )
    
    system_prompt = (
        "Bạn là Giám đốc Sáng tạo. Dựa vào kịch bản video, hãy chọn worker_type phù hợp nhất.\n"
        "Các lựa chọn: review, unbox_viral, slideshow, translify.\n"
        "Trả về DUY NHẤT một chuỗi JSON sạch dạng: {\"worker_type\": \"...\"}"
    )
    
    user_content = (
        f"Tiêu đề: {ctx['title']}\n"
        f"Kịch bản: {ctx['script_content']}\n"
        f"Tóm tắt: {ctx['master_contents_brief']}\n"
    )
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content)
    ])
    
    parsed = extract_json_from_text(response.content)
    worker_type = parsed.get("worker_type", "slideshow")
    
    if worker_type not in VALID_WORKER_TYPES:
        worker_type = "slideshow"
        
    save_node_log(
        job_id=state["job_id"],
        node_name="router",
        step="decide",
        input_data={"title": ctx["title"], "script_content": ctx["script_content"], "master_contents_brief": ctx["master_contents_brief"]},
        output_data={"worker_type": worker_type},
        llm_reasoning=response.content
    )
        
    return {"worker_type": worker_type}

def draft_generator_node(state: LeaderAgentState) -> Dict[str, Any]:
    """
    LLM node to generate full video configurations.
    Uses RAW TEXT extraction to bypass JSON-in-JSON escaping issues.
    """
    logger.info(f"Node: draft_generator_node (attempt {state['attempts'] + 1})")
    ctx = state["context"]
    user_id = state["user_id"]
    worker_type = state["worker_type"]
    pacing_errors = state.get("pacing_errors", [])
    
    config = resolve_llm_config(user_id, LLMFeature.LEADER_ANALYSIS)
    llm = ChatOpenAI(
        model=config["model_name"],
        openai_api_base=f"{config['base_url'].rstrip('/')}/v1",
        openai_api_key=config["api_key"] or "ollama",
        temperature=0.7 # Higher temperature for creativity in viral optimization
    )
    
    system_prompt = load_prompt("leader_system_prompt.txt")
    
    # ── User Prompt Construction ──────────────────────────────────────────────
    from worker_leader.leader_runner import _build_user_prompt
    user_content = _build_user_prompt(ctx)
    
    # Add refinement instructions if this is a retry
    if pacing_errors:
        error_msg = "\n".join(pacing_errors)
        user_content += (
            f"\n\n--- THÔNG BÁO LỖI TỪ HỆ THỐNG (LẦN THỬ {state['attempts']}) ---\n"
            f"Kịch bản trước đó của bạn có lỗi nhịp độ chữ (quá nhanh):\n{error_msg}\n"
            f"HÃY SỬA LẠI: Chia nhỏ các câu dài, hoặc tăng thời lượng (duration) của các phân cảnh bị lỗi. "
            f"Đảm bảo nhịp độ < 4.5 từ/giây."
        )

    # Invoke LLM
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content)
    ])
    
    # ── Robust Extraction with Retry Logic ────────────────────────────────────
    try:
        # Extract JSON from Markdown block or raw text
        parsed_res = extract_json_from_text(response.content)
        
        save_node_log(
            job_id=state["job_id"],
            node_name="generator",
            step="generate",
            input_data={"prompt": user_content, "attempts": state["attempts"] + 1},
            output_data={"ai_metadata": parsed_res.get("ai_metadata"), "draft_variants": parsed_res.get("draft_variants")},
            llm_reasoning=response.content
        )
    except Exception as e:
        logger.error(f"JSON Parsing Error (Attempt {state['attempts'] + 1}): {e}")
        
        save_node_log(
            job_id=state["job_id"],
            node_name="generator",
            step="generate",
            input_data={"prompt": user_content, "attempts": state["attempts"] + 1},
            output_data={"error": f"JSON Syntax Error: {str(e)}"},
            llm_reasoning=response.content,
            log_level="WARNING"
        )
        
        # If parsing fails, we treat it as a "system error" and trigger a retry
        # The next attempt will see this error message in the prompt
        return {
            "pacing_errors": state.get("pacing_errors", []) + [f"LỖI CÚ PHÁP JSON: {str(e)}. Hãy chắc chắn bạn bọc kịch bản trong block ```json ... ``` và dùng đúng ngoặc kép."],
            "attempts": state["attempts"] + 1
        }
    
    return {
        "ai_metadata": parsed_res.get("ai_metadata", {}),
        "draft_variants": parsed_res.get("draft_variants", {}),
        "attempts": state["attempts"] + 1
    }

def pacing_validator_node(state: LeaderAgentState) -> Dict[str, Any]:
    """Python node to validate pacing. Populates pacing_errors if any."""
    logger.info("Node: pacing_validator_node")
    draft_variants = state.get("draft_variants", {})
    viral_optimized = draft_variants.get("viral_optimized", {})
    
    errors = []
    res = validate_video_pacing(json.dumps(viral_optimized))
    if "vượt quá" in res.lower() or "lỗi" in res.lower():
        errors = res.split("\n")
            
    save_node_log(
        job_id=state["job_id"],
        node_name="validator",
        step="validate",
        input_data={"viral_optimized": viral_optimized},
        output_data={"pacing_errors": errors},
        llm_reasoning=f"Kiểm thử nhịp độ chữ hoàn tất. Phát hiện {len(errors)} cảnh quá nhanh."
    )
            
    return {"pacing_errors": errors}


def healing_node(state: LeaderAgentState) -> Dict[str, Any]:
    """Python node to apply defensive healing to JSON structures."""
    logger.info("Node: healing_node")
    
    worker_type = state["worker_type"]
    ctx = state["context"]
    ai_metadata = state.get("ai_metadata", {})
    draft_variants = state.get("draft_variants", {})
    payload = state["raw_payload"]
    
    # 1. Sync metadata
    if not isinstance(ai_metadata, dict): ai_metadata = {}
    ai_metadata["funnel_stage"] = ctx["funnel_stage"]
    ai_metadata["psych_angle"] = ctx["psych_angle"]
    ai_metadata["content_brief_context"] = ctx["content_brief_context"]
    if "hook_score" not in ai_metadata: ai_metadata["hook_score"] = 7
    
    # 2. Heal variants
    script_content = ctx["script_content"]
    title = ctx["title"]
    
    original_draft = heal_draft_parameters(worker_type, draft_variants.get("original", {}), script_content, title)
    viral_draft = heal_draft_parameters(worker_type, draft_variants.get("viral_optimized", {}), script_content, title)
    
    # Inject TMCP context
    for draft in [original_draft, viral_draft]:
        if "metadata" not in draft or not isinstance(draft["metadata"], dict):
            draft["metadata"] = {}
        draft["metadata"]["tmcp_context"] = payload

    healed_variants = {
        "original": original_draft,
        "viral_optimized": viral_draft
    }

    save_node_log(
        job_id=state["job_id"],
        node_name="healing",
        step="heal",
        input_data={"original": draft_variants.get("original"), "viral_optimized": draft_variants.get("viral_optimized")},
        output_data={"original": original_draft, "viral_optimized": viral_draft},
        llm_reasoning="Đã chạy các healer phòng thủ để chuẩn hóa cấu trúc JSON và chèn TMCP Context."
    )

    return {
        "worker_type": worker_type,
        "ai_metadata": ai_metadata,
        "draft_variants": healed_variants
    }

def persistence_node(state: LeaderAgentState) -> Dict[str, Any]:
    """Save the final result to DB."""
    logger.info("Node: persistence_node")
    from worker_leader.leader_runner import _create_draft_job
    
    db = SessionLocal()
    try:
        # Load parent job
        parent_job = db.query(VideoJob).filter(VideoJob.id == state["job_id"]).first()
        if not parent_job:
            raise ValueError(f"Parent job {state['job_id']} not found")
            
        new_job = _create_draft_job(
            db=db,
            parent_job=parent_job,
            worker_type=state["worker_type"],
            ai_metadata=state["ai_metadata"],
            draft_variants=state["draft_variants"],
            payload=state["raw_payload"]
        )
        
        save_node_log(
            job_id=state["job_id"],
            node_name="persistence",
            step="persist",
            input_data={"worker_type": state["worker_type"]},
            output_data={"created_draft_job_id": new_job.id},
            llm_reasoning="Đã tạo Job DRAFT thành công trong cơ sở dữ liệu."
        )
        
        return {"final_job_id": new_job.id}
    finally:
        db.close()
