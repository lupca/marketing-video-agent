"""
Leader Runner — Processes script analysis jobs for the AI Leader Agent.
"""

import os
import json
import logging
import time
import requests
import re
from typing import Dict, Any
from datetime import datetime, timezone

from smolagents import CodeAgent, OpenAIServerModel, tool, ToolCallingAgent

from shared_core.database import SessionLocal
from shared_core.models import VideoJob, JobLog
from shared_core.config import get_settings
from shared_core.llm_resolver import resolve_llm_config
from shared_core.constants import LLMFeature

logger = logging.getLogger(__name__)


@tool
def validate_video_pacing(timeline_script_str: str) -> str:
    """
    Quét kịch bản timeline dạng JSON, đếm số từ trên giây (words per second) ở mỗi phân cảnh.
    Nếu có phân cảnh vượt quá 4.5 từ/giây, cảnh báo cho LLM và yêu cầu LLM chia đôi phân cảnh đó hoặc rút gọn văn bản.
    
    Args:
        timeline_script_str: Kịch bản timeline dưới dạng chuỗi JSON string cần kiểm tra.
    """
    try:
        data = json.loads(timeline_script_str)
        warnings = []
        segments = []
        
        # Hỗ trợ cấu trúc timeline_script hoặc input_json.products hoặc text_events
        if isinstance(data, list):
            segments = data
        elif isinstance(data, dict):
            if "timeline_script" in data:
                segments = data["timeline_script"]
            elif "input_json" in data and "products" in data["input_json"]:
                for idx, p in enumerate(data["input_json"]["products"]):
                    segments.append({
                        "segment": p.get("hook", f"slide_{idx+1}"),
                        "text_overlay": p.get("text", ""),
                        "time_range": [0, 5]
                    })
            elif "text_events" in data:
                events = data["text_events"]
                for i, ev in enumerate(events):
                    nxt_time = events[i+1]["time"] if i < len(events) - 1 else ev["time"] + 4.0
                    duration = max(nxt_time - ev["time"], 1.0)
                    segments.append({
                        "segment": f"event_{i+1}",
                        "text_overlay": ev.get("text", ""),
                        "time_range": [ev["time"], ev["time"] + duration]
                    })
            else:
                return "Cấu trúc JSON không chứa timeline_script hoặc products/text_events để kiểm tra."
        else:
            return "timeline_script_str không phải là một JSON valid."
            
        for seg in segments:
            if not isinstance(seg, dict):
                continue
            name = seg.get("segment") or seg.get("video_source") or "unnamed"
            text = seg.get("text_overlay") or seg.get("text") or ""
            time_range = seg.get("time_range")
            if not text or not time_range or len(time_range) < 2:
                continue
            
            duration = max(float(time_range[1]) - float(time_range[0]), 0.5)
            word_count = len(text.split())
            wps = word_count / duration
            
            if wps > 4.5:
                warnings.append(
                    f"Phân cảnh '{name}' quá nhanh: {wps:.2f} từ/giây (vượt quá giới hạn 4.5 từ/giây). "
                    f"Số từ: {word_count}, Thời lượng: {duration}s. Hãy chia đôi cảnh này hoặc giảm bớt chữ trong text_overlay."
                )
                
        if warnings:
            return "\n".join(warnings)
        return "Tất cả các phân cảnh đều có nhịp độ (pacing) hợp lý, dưới 4.5 từ/giây."
    except Exception as e:
        return f"Lỗi khi kiểm tra pacing: {str(e)}"


def _extract_json_from_text(text: str) -> dict:
    """Tìm và parse JSON từ văn bản kết quả của LLM/Agent."""
    try:
        return json.loads(text.strip())
    except Exception:
        pass
        
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass
            
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass
            
    raise ValueError(f"Không thể trích xuất JSON hợp lệ từ kết quả của Agent: {text}")


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


# ── System Settings DB Helper ───────────────────────────────────────────────

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


# ── Defensive Healers ─────────────────────────────────────────────────────────

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

    review_points = []
    if "review_points" in draft_params and isinstance(draft_params["review_points"], list):
        review_points = draft_params["review_points"]
    elif "points" in draft_params and isinstance(draft_params["points"], list):
        review_points = draft_params["points"]
        
    if ("timeline_script" not in draft_params or not isinstance(draft_params["timeline_script"], list)) and review_points:
        timeline_script = []
        for idx, pt in enumerate(review_points):
            timeline_script.append({
                "segment": f"0{idx+1}_point" if idx < 9 else f"{idx+1}_point",
                "video_source": "1",
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

    if "timeline_script" not in draft_params or not isinstance(draft_params["timeline_script"], list) or len(draft_params["timeline_script"]) == 0:
        timeline_script = []
        for idx, sen in enumerate(sentences[:5]):
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

    draft_params.pop("review_points", None)
    draft_params.pop("points", None)
    return draft_params


def _heal_slideshow(draft_params: dict, sentences: list, title: str) -> dict:
    """Logic sửa lỗi phòng thủ cho worker slideshow."""
    if "input_json" not in draft_params or not isinstance(draft_params["input_json"], dict):
        draft_params["input_json"] = {}
    input_json = draft_params["input_json"]

    if "products" in draft_params and "products" not in input_json:
        input_json["products"] = draft_params.pop("products")

    if "intro_text" not in input_json or not input_json["intro_text"]:
        input_json["intro_text"] = title or "Chào mừng đến với " + (sentences[0][:20] if sentences else "Video")
    if "outro_text" not in input_json or not input_json["outro_text"]:
        input_json["outro_text"] = "Mua ngay tại giỏ hàng bên dưới!"

    if "products" not in input_json or not isinstance(input_json["products"], list) or len(input_json["products"]) == 0:
        products = []
        for idx, sen in enumerate(sentences[:4]):
            products.append({
                "image": f"https://images.unsplash.com/photo-{1523275335684 + idx * 1000}-37898b6baf30?w=500",
                "text": sen,
                "hook": f"Đặc điểm {idx+1}"
            })
        input_json["products"] = products

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
    """Hậu xử lý và chuẩn hóa draft_parameters."""
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


# ── Ollama API Call ───────────────────────────────────────────────────────────

def call_ollama_with_retry(api_url: str, req_payload: dict, headers: dict, retries: int = 3, backoff: float = 2.0) -> dict:
    """Gọi API Ollama kèm Exponential Backoff."""
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


# ── Leader Execution ──────────────────────────────────────────────────────────

def process_leader_job_impl(job_id: int):
    """
    Leader Agent: Phân tích kịch bản và tạo Job mới ở trạng thái DRAFT.
    """
    db = SessionLocal()
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found in database.")
        db.close()
        return

    try:
        import sys
        if not hasattr(sys.stdout, "fileno"):
            sys.stdout.fileno = lambda: 1
        if not hasattr(sys.stderr, "fileno"):
            sys.stderr.fileno = lambda: 2

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
        variant = payload.get("variant_data", {}) or {}
        
        brand_name = brand.get("brand_name", "")
        tone = brand.get("tone_of_voice", "")
        colors = brand.get("brand_colors", [])
        
        campaign_name = campaign.get("campaign_name", "")
        audience = campaign.get("target_audience", "")
        objective = campaign.get("objective", "")
        
        title = payload.get("title") or variant.get("title", "")
        script_content = payload.get("script_content") or variant.get("script_content", "")
        hints = payload.get("media_hints") or variant.get("media_hints", [])
        duration = payload.get("suggested_duration") or variant.get("suggested_duration", 15)
        
        # New TMCP Funnel & Content Brief Context Fields
        content_brief_context = payload.get("content_brief_context", {}) or {}
        angle_name = content_brief_context.get("angle_name") or ""
        funnel_stage_cb = content_brief_context.get("funnel_stage") or ""
        psychological_angle = content_brief_context.get("psychological_angle") or ""
        pain_point_focus = content_brief_context.get("pain_point_focus") or ""
        key_message_variation = content_brief_context.get("key_message_variation") or ""
        call_to_action_direction = content_brief_context.get("call_to_action_direction") or ""
        brief = content_brief_context.get("brief") or ""

        funnel_stage = funnel_stage_cb or payload.get("funnel_stage") or campaign.get("funnel_stage") or "Unknown"
        psych_angle = psychological_angle or payload.get("psych_angle") or campaign.get("psych_angle") or ""
        master_contents_brief = brief or payload.get("master_contents_brief") or variant.get("master_contents_brief") or ""

        # 3. Gọi SmolAgents CodeAgent
        user_id = job.project.user_id if job.project else None
        config = resolve_llm_config(user_id, LLMFeature.LEADER_ANALYSIS)
        
        base_url = config["base_url"]
        model_name = config["model_name"]
        api_key = config["api_key"] or "ollama"
        
        system_prompt = load_prompt("leader_system_prompt.txt")

        user_content = (
            f"--- CONTENT BRIEFS TỪ TMCP ---\n"
            f"- Phễu Marketing: {funnel_stage} | Tâm lý học hành vi: {psych_angle}\n"
        )
        if angle_name:
            user_content += f"- Góc tiếp cận chiến dịch: {angle_name}\n"
        if pain_point_focus:
            user_content += f"- Nỗi đau khách hàng tập trung: {pain_point_focus}\n"
        if key_message_variation:
            user_content += f"- Thông điệp cốt lõi: {key_message_variation}\n"
        if call_to_action_direction:
            user_content += f"- Hướng đi kêu gọi hành động (CTA): {call_to_action_direction}\n"

        user_content += (
            f"- Tóm tắt nội dung chính (Master Brief): {master_contents_brief}\n"
            f"- Thương hiệu: {brand_name}\n"
            f"- Tone giọng: {tone}\n"
            f"- Màu sắc: {colors}\n"
            f"- Chiến dịch: {campaign_name}\n"
            f"- Đối tượng: {audience}\n"
            f"- Mục tiêu: {objective}\n"
            f"- Tiêu đề kịch bản: {title}\n"
            f"- Kịch bản gốc: {script_content}\n"
            f"- Gợi ý phân cảnh: {hints}\n"
            f"- Thời lượng gợi ý: {duration} giây\n\n"
            f"Bạn PHẢI sử dụng công cụ `validate_video_pacing` để tự động kiểm tra nhịp độ chữ của timeline script do bạn sinh ra. "
            f"Nếu công cụ báo lỗi (vượt quá 4.5 từ/giây), hãy tự động điều chỉnh kịch bản hoặc tăng thời lượng phân cảnh và chạy lại công cụ cho đến khi đạt yêu cầu.\n"
            f"Hãy hoàn thành nhiệm vụ và xuất ra kết quả JSON duy nhất theo đúng cấu trúc yêu cầu."
        )

        logger.info(f"Setting up SmolAgents CodeAgent with model {model_name} from {config['source']} at {base_url}")
        
        model = OpenAIServerModel(
            model_id=model_name,
            api_base=f"{base_url.rstrip('/')}/v1",
            api_key=api_key,
        )
        
        agent = ToolCallingAgent(
            tools=[validate_video_pacing],
            model=model,
            instructions=system_prompt,
            max_steps=3,
        )

        logger.info(f"Running agent...")
        agent_result = agent.run(user_content)
        logger.info(f"Agent finished. Result: {agent_result}")

        # Parse AI response
        parsed_res = _extract_json_from_text(agent_result)
        worker_type = parsed_res.get("worker_type", "slideshow")
        ai_metadata = parsed_res.get("ai_metadata", {})
        draft_variants = parsed_res.get("draft_variants", {})

        # Tự động đồng bộ các trường phân tích vào ai_metadata nếu thiếu
        if not isinstance(ai_metadata, dict):
            ai_metadata = {}
        ai_metadata["funnel_stage"] = funnel_stage
        ai_metadata["psych_angle"] = psych_angle
        ai_metadata["content_brief_context"] = content_brief_context
        if "hook_score" not in ai_metadata:
            ai_metadata["hook_score"] = 7
        if "seo_titles" not in ai_metadata:
            ai_metadata["seo_titles"] = [title]
        if "qa_warnings" not in ai_metadata:
            ai_metadata["qa_warnings"] = []

        valid_workers = ["slideshow", "review", "unbox_viral", "translify"]
        if worker_type not in valid_workers:
            logger.warning(f"Invalid worker_type '{worker_type}' returned, defaulting to 'slideshow'")
            worker_type = "slideshow"

        # Apply healers to both draft variants to guarantee integrity
        logger.info(f"Applying defensive healing to both draft variants for worker: {worker_type}")
        if not isinstance(draft_variants, dict):
            draft_variants = {}
        
        original_draft = draft_variants.get("original", {})
        viral_draft = draft_variants.get("viral_optimized", {})
        
        original_draft = heal_draft_parameters(worker_type, original_draft, script_content, title)
        viral_draft = heal_draft_parameters(worker_type, viral_draft, script_content, title)
        
        if "metadata" not in original_draft or not isinstance(original_draft["metadata"], dict):
            original_draft["metadata"] = {}
        original_draft["metadata"]["tmcp_context"] = payload

        if "metadata" not in viral_draft or not isinstance(viral_draft["metadata"], dict):
            viral_draft["metadata"] = {}
        viral_draft["metadata"]["tmcp_context"] = payload

        draft_variants["original"] = original_draft
        draft_variants["viral_optimized"] = viral_draft

        # 4. Tạo Job mới ở trạng thái DRAFT với các trường nâng cấp mới
        new_job = VideoJob(
            job_type=worker_type,
            project_id=job.project_id,
            status="DRAFT",
            priority=0,
            # config_data tạm thời để trống (None) như mô tả trong Phase 1 Spec
            config_data=None,
            draft_parameters=original_draft, # giữ tương thích ngược
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

        # 5. Ghi log phân tích vào Job chính
        db_log = JobLog(
            job_id=job.id,
            log_level="INFO",
            message=f"Leader Agent selected worker: {worker_type}. Created Draft Job ID: {new_job.id}"
        )
        db.add(db_log)

        # 6. Đánh dấu Job chính là COMPLETED
        job.status = "COMPLETED"
        job.progress_percent = 100
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Leader Agent task completed successfully for job: {job_id}")

    except Exception as e:
        logger.error(f"Error in process_leader_job_impl: {str(e)}", exc_info=True)
        job.status = "FAILED"
        job.error_message = f"Leader Agent Error: {str(e)}"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

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
