"""
Leader Runner — Processes script analysis jobs for the AI Leader Agent.

This module is the main entry point for the Leader Agent worker.
It orchestrates:
  1. Payload extraction from a VideoJob's config_data.
  2. Prompt construction with TMCP content brief context.
  3. SmolAgents ToolCallingAgent execution.
  4. Result parsing, healing, and DRAFT job creation.

Submodules:
  - ``worker_leader.tools``   — SmolAgents tool definitions.
  - ``worker_leader.healers`` — Defensive draft parameter healers.
  - ``worker_leader.utils``   — JSON, prompt, and DB utilities.
"""

import json
import logging
import sys
import time
import requests
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog
from shared_core.config import get_settings
from shared_core.llm_resolver import resolve_llm_config
from shared_core.constants import LLMFeature

from worker_leader.leader_graph import leader_graph
from worker_leader.tools import validate_video_pacing
from worker_leader.healers import heal_draft_parameters
from worker_leader.healers.dispatcher import VALID_WORKER_TYPES
from worker_leader.utils import extract_json_from_text, load_prompt

logger = logging.getLogger(__name__)


# ── Payload Context ───────────────────────────────────────────────────────────


def _extract_payload_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize all context fields from the raw job payload.

    Returns a flat dictionary with brand, campaign, content brief, and script fields.
    """
    brand = payload.get("brand_context", {})
    campaign = payload.get("campaign_context", {})
    variant = payload.get("variant_data", {}) or {}

    # Content Brief Context (new TMCP structure)
    content_brief_context = payload.get("content_brief_context", {}) or {}
    angle_name = content_brief_context.get("angle_name") or ""
    funnel_stage_cb = content_brief_context.get("funnel_stage") or ""
    psychological_angle = content_brief_context.get("psychological_angle") or ""
    pain_point_focus = content_brief_context.get("pain_point_focus") or ""
    key_message_variation = content_brief_context.get("key_message_variation") or ""
    call_to_action_direction = content_brief_context.get("call_to_action_direction") or ""
    brief = content_brief_context.get("brief") or ""

    # Backwards-compatible funnel / psych / brief resolution
    funnel_stage = funnel_stage_cb or payload.get("funnel_stage") or campaign.get("funnel_stage") or "Unknown"
    psych_angle = psychological_angle or payload.get("psych_angle") or campaign.get("psych_angle") or ""
    master_contents_brief = brief or payload.get("master_contents_brief") or variant.get("master_contents_brief") or ""

    title = payload.get("title") or variant.get("title", "")
    script_content = payload.get("script_content") or variant.get("script_content", "")

    return {
        "brand_name": brand.get("brand_name", ""),
        "tone": brand.get("tone_of_voice", ""),
        "colors": brand.get("brand_colors", []),
        "campaign_name": campaign.get("campaign_name", ""),
        "audience": campaign.get("target_audience", ""),
        "objective": campaign.get("objective", ""),
        "title": title,
        "script_content": script_content,
        "hints": payload.get("media_hints") or variant.get("media_hints", []),
        "duration": payload.get("suggested_duration") or variant.get("suggested_duration", 15),
        "funnel_stage": funnel_stage,
        "psych_angle": psych_angle,
        "master_contents_brief": master_contents_brief,
        "content_brief_context": content_brief_context,
        "angle_name": angle_name,
        "pain_point_focus": pain_point_focus,
        "key_message_variation": key_message_variation,
        "call_to_action_direction": call_to_action_direction,
    }


# ── Prompt Builder ────────────────────────────────────────────────────────────


def _build_user_prompt(ctx: Dict[str, Any]) -> str:
    """
    Build the user-facing prompt string from extracted context.

    The prompt includes TMCP content brief fields (when present),
    brand/campaign details, and the pacing-validation instruction.
    """
    user_content = (
        f"--- CONTENT BRIEFS TỪ TMCP ---\n"
        f"- Phễu Marketing: {ctx['funnel_stage']} | Tâm lý học hành vi: {ctx['psych_angle']}\n"
    )
    if ctx["angle_name"]:
        user_content += f"- Góc tiếp cận chiến dịch: {ctx['angle_name']}\n"
    if ctx["pain_point_focus"]:
        user_content += f"- Nỗi đau khách hàng tập trung: {ctx['pain_point_focus']}\n"
    if ctx["key_message_variation"]:
        user_content += f"- Thông điệp cốt lõi: {ctx['key_message_variation']}\n"
    if ctx["call_to_action_direction"]:
        user_content += f"- Hướng đi kêu gọi hành động (CTA): {ctx['call_to_action_direction']}\n"

    user_content += (
        f"- Tóm tắt nội dung chính (Master Brief): {ctx['master_contents_brief']}\n"
        f"- Thương hiệu: {ctx['brand_name']}\n"
        f"- Tone giọng: {ctx['tone']}\n"
        f"- Màu sắc: {ctx['colors']}\n"
        f"- Chiến dịch: {ctx['campaign_name']}\n"
        f"- Đối tượng: {ctx['audience']}\n"
        f"- Mục tiêu: {ctx['objective']}\n"
        f"- Tiêu đề kịch bản: {ctx['title']}\n"
        f"- Kịch bản gốc: {ctx['script_content']}\n"
        f"- Gợi ý phân cảnh: {ctx['hints']}\n"
        f"- Thời lượng gợi ý: {ctx['duration']} giây\n\n"
        f"Bạn PHẢI sử dụng công cụ `validate_video_pacing` để tự động kiểm tra nhịp độ chữ của timeline script do bạn sinh ra. "
        f"Nếu công cụ báo lỗi (vượt quá 4.5 từ/giây), hãy tự động điều chỉnh kịch bản hoặc tăng thời lượng phân cảnh và chạy lại công cụ cho đến khi đạt yêu cầu.\n"
        f"Hãy hoàn thành nhiệm vụ và xuất ra kết quả JSON duy nhất theo đúng cấu trúc yêu cầu."
    )
    return user_content


# ── Result Parsing & Healing ────────────────────────────────────────────────


def _parse_and_heal_result(
    agent_result: str,
    ctx: Dict[str, Any],
    payload: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Parse the agent JSON output, validate worker_type, sync ai_metadata,
    and apply defensive healers to both draft variants.

    Returns:
        (worker_type, ai_metadata, draft_variants)
    """
    parsed_res = extract_json_from_text(agent_result)
    worker_type = parsed_res.get("worker_type", "slideshow")
    ai_metadata = parsed_res.get("ai_metadata", {})
    draft_variants = parsed_res.get("draft_variants", {})

    # Sync analysis fields into ai_metadata
    if not isinstance(ai_metadata, dict):
        ai_metadata = {}
    ai_metadata["funnel_stage"] = ctx["funnel_stage"]
    ai_metadata["psych_angle"] = ctx["psych_angle"]
    ai_metadata["content_brief_context"] = ctx["content_brief_context"]
    if "hook_score" not in ai_metadata:
        ai_metadata["hook_score"] = 7
    if "seo_titles" not in ai_metadata:
        ai_metadata["seo_titles"] = [ctx["title"]]
    if "qa_warnings" not in ai_metadata:
        ai_metadata["qa_warnings"] = []

    # Validate worker_type
    if worker_type not in VALID_WORKER_TYPES:
        logger.warning(f"Invalid worker_type '{worker_type}' returned, defaulting to 'slideshow'")
        worker_type = "slideshow"

    # Heal both draft variants
    logger.info(f"Applying defensive healing to both draft variants for worker: {worker_type}")
    if not isinstance(draft_variants, dict):
        draft_variants = {}

    script_content = ctx["script_content"]
    title = ctx["title"]

    original_draft = heal_draft_parameters(worker_type, draft_variants.get("original", {}), script_content, title)
    viral_draft = heal_draft_parameters(worker_type, draft_variants.get("viral_optimized", {}), script_content, title)

    # Embed TMCP context into each variant's metadata
    if "metadata" not in original_draft or not isinstance(original_draft["metadata"], dict):
        original_draft["metadata"] = {}
    original_draft["metadata"]["tmcp_context"] = payload

    if "metadata" not in viral_draft or not isinstance(viral_draft["metadata"], dict):
        viral_draft["metadata"] = {}
    viral_draft["metadata"]["tmcp_context"] = payload

    draft_variants["original"] = original_draft
    draft_variants["viral_optimized"] = viral_draft

    return worker_type, ai_metadata, draft_variants


# ── Draft Job Creation ───────────────────────────────────────────────────────


def _create_draft_job(
    db,
    parent_job: VideoJob,
    worker_type: str,
    ai_metadata: Dict[str, Any],
    draft_variants: Dict[str, Any],
    payload: Dict[str, Any],
) -> VideoJob:
    """
    Persist a new VideoJob in DRAFT status with all upgraded fields.
    """
    new_job = VideoJob(
        job_type=worker_type,
        project_id=parent_job.project_id,
        status="DRAFT",
        priority=0,
        config_data=None,
        draft_parameters=draft_variants.get("original", {}),
        ai_metadata=ai_metadata,
        tmcp_source_config=payload,
        draft_variants=draft_variants,
        progress_percent=0,
        note=f"Draft generated by Leader Agent for Variant: {payload.get('source_id') or 'manual'}",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    logger.info(f"Created DRAFT job {new_job.id} for worker {worker_type}")
    return new_job


# ── Main Entry Point ─────────────────────────────────────────────────────────


def process_leader_job_impl(job_id: int):
    """
    Leader Agent: Phân tích kịch bản và tạo Job mới ở trạng thái DRAFT.
    Sử dụng LangGraph để quản lý luồng lặp và tự sửa lỗi (Self-healing).
    """
    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found in database.")
        db.close()
        return

    try:
        # Patch stdout/stderr for environments without real file descriptors
        if not hasattr(sys.stdout, "fileno"):
            sys.stdout.fileno = lambda: 1
        if not hasattr(sys.stderr, "fileno"):
            sys.stderr.fileno = lambda: 2

        logger.info(f"Leader Agent starting LangGraph analysis for job: {job_id}")
        job.status = "PROCESSING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        # 1. Prepare initial state
        payload = job.config_data
        if not payload:
            raise ValueError("No payload found in config_data")
        if isinstance(payload, str):
            payload = json.loads(payload)

        initial_state = {
            "raw_payload": payload,
            "job_id": job_id,
            "user_id": job.project.user_id if job.project else None,
            "attempts": 0
        }

        # 2. Stream LangGraph (stream_mode="values" to yield full state snapshot)
        # Chạy Graph trần (Stateless) bên trong Celery Worker để tránh xung đột DB
        final_state = initial_state
        for event in leader_graph.stream(initial_state, stream_mode="values"):
            final_state = event
        
        final_job_id = final_state.get("final_job_id")

        # 3. Mark parent job completed
        job.status = "COMPLETED"
        job.progress_percent = 100
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        logger.info(f"Leader Agent task completed successfully. Created Draft Job ID: {final_job_id}")

    except Exception as e:
        logger.error(f"Error in process_leader_job_impl (LangGraph): {str(e)}", exc_info=True)
        job.status = "FAILED"
        job.error_message = f"Leader Agent Error: {str(e)}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        try:
            db_log = JobLog(
                job_id=job.id,
                log_level="ERROR",
                message=f"Leader Agent failed: {str(e)}",
            )
            db.add(db_log)
            db.commit()
        except Exception as log_ex:
            logger.error(f"Failed to log error to DB: {log_ex}")

    finally:
        db.close()


# ── Legacy API (kept for potential external callers) ─────────────────────────


def call_ollama_with_retry(
    api_url: str,
    req_payload: dict,
    headers: dict,
    retries: int = 3,
    backoff: float = 2.0,
) -> dict:
    """Gọi API Ollama kèm Exponential Backoff (legacy, currently unused)."""
    last_error = None
    for attempt in range(retries):
        try:
            res = requests.post(api_url, json=req_payload, headers=headers, timeout=60)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            last_error = e
            wait_time = backoff * (2 ** attempt)
            logger.warning(
                f"Ollama call failed (Attempt {attempt+1}/{retries}). "
                f"Retrying in {wait_time}s... Error: {e}"
            )
            time.sleep(wait_time)
    raise RuntimeError(f"Ollama API unavailable after {retries} retries. Last error: {last_error}")
