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
from typing import Dict, Any
from datetime import datetime, timezone

from smolagents import CodeAgent, OpenAIServerModel
from smolagents.memory import ActionStep, PlanningStep

from shared_core.database import SessionLocal
from shared_core.models import AgentSession, AgentLog
from shared_core.config import get_settings

from worker_agent.tools import (
    YouTubeSearchTool, DownloadVideoTool, AnalyzeVideoTool,
    YouTubeAudioSearchTool, GenerateVideoTool
)

logger = logging.getLogger(__name__)

AGENT_INSTRUCTIONS = """\
Bạn là Agent tự động hóa Video Creator trên một nền tảng tạo video ngắn AI. 
Nhiệm vụ: Tìm video viral, tải về, phân tích, tìm nhạc nền phù hợp, và giao task tạo video.

QUY TRÌNH BẮT BUỘC BẠN PHẢI TUÂN THỦ NGHIÊM NGẶT (Step-by-step):
1. Dùng `youtube_search` với keyword để lấy danh sách top video Shorts.
2. Chọn video tốt nhất đầu tiên, dùng `download_media` (format_type="video") để tải về MinIO, lấy được result_url (hay s3_url). Tham số `url` LÀ BẮT BUỘC.
3. Dùng `analyze_video` truyền s3_url video vừa tải để lấy được JSON thông tin chi tiết (độ phân giải, scene_count, chuyển động).
4. Dùng `youtube_audio_search` kết hợp với keyword để tìm nhạc nền hợp lí.
5. Chọn 1 bản nhạc tốt, dùng `download_media` (format_type="audio") tải bản nhạc đó về, lấy được result_url của nhạc. Tham số `url` LÀ BẮT BUỘC.
6. Lựa chọn Worker Type (bắt buộc phải là "promotion", "slideshow", "review", hoặc "unbox_viral") dựa trên content_type_hints từ bước analyze.
7. Dùng `generate_video` gửi yêu cầu (bao gồm worker_type, config_data_json).
Config data bắt buộc phải là chuỗi JSON hợp lệ. Format CỦA config_data_json PHỤ THUỘC VÀO TỪNG WORKER NHƯ SAU:
   - Nếu worker_type là "unbox_viral": `{"video": "<s3_url_video>", "audio": "<s3_url_audio>"}`
   - Nếu worker_type là "slideshow": `{"products": [{"image": "<s3_url_video_hoac_anh>", "text": "Deal hot", "hook": "Mua ngay"}], "intro_text": "Top Video", "outro_text": "Follow me"}`
   - Nếu worker_type là "promotion": `{"images": ["<s3_url_video_hoac_anh>"]}`
   - Nếu worker_type là "review": `{"assets": {"audio": {"bgm_path": "<s3_url_audio>"}, "video_folders": {"1": "<s3_url_video>"}}}`
Ví dụ: gọi `generate_video(..., config_data_json=json.dumps({"video": "<s3_url_video>", "audio": "<s3_url_audio>"}), ...)`
Tuyệt đối KHÔNG dùng `str(config_data)` vì nó sẽ gây lỗi parse JSON.

LƯU Ý ĐẶC BIỆT:
- KHÔNG BỊA ĐẶT kết quả mà chưa gọi Tool.
- Hãy chạy từng bước thông qua việc thực thi đoạn code python nhỏ (CodeAgent).
- Nếu tool trả về lỗi, hãy in lỗi hoặc phân tích lý do và thử video tiếp theo.
"""

AGENT_INSTRUCTIONS_RESEARCH_ONLY = """\
Bạn là Agent tự động hóa Video Creator trên một nền tảng tạo video ngắn AI.
Nhiệm vụ: Tìm video viral, tải về, phân tích, tìm nhạc nền phù hợp và CHỈ tải về nhạc, video. KHÔNG generate video.

QUY TRÌNH BẮT BUỘC BẠN PHẢI TUÂN THỦ NGHIÊM NGẶT (Step-by-step):
1. Dùng `youtube_search` với keyword để lấy danh sách top video Shorts.
2. Chọn video tốt nhất đầu tiên, dùng `download_media` (format_type="video") để tải về MinIO, lấy được result_url (hay s3_url). Tham số `url` LÀ BẮT BUỘC.
3. Dùng `analyze_video` truyền s3_url video vừa tải để lấy được JSON thông tin chi tiết (độ phân giải, scene_count, chuyển động).
4. Dùng `youtube_audio_search` kết hợp với keyword để tìm nhạc nền hợp lí.
5. Chọn 1 bản nhạc tốt, dùng `download_media` (format_type="audio") tải bản nhạc đó về, lấy được result_url của nhạc. Tham số `url` LÀ BẮT BUỘC.
6. Nếu đã xác định được s3_url của video và audio, HÃY DỪNG LẠI và tóm tắt thành công với kết quả tải về.

LƯU Ý ĐẶC BIỆT:
- KHÔNG BỊA ĐẶT kết quả mà chưa gọi Tool.
- Hãy chạy từng bước thông qua việc thực thi đoạn code python nhỏ (CodeAgent).
- Nếu tool trả về lỗi, hãy in lỗi hoặc phân tích lý do và thử video tiếp theo.
- Hãy cung cấp đường dẫn s3_url của cả video và audio ở đầu ra hoặc tóm tắt công việc của bạn ở những bước cuối cùng.
"""


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


# ── Agent Factory ─────────────────────────────────────────────────────────────

def create_agent(session_id: str = None, mode: str = "full"):
    """
    Create a CodeAgent configured for local Ollama LLM.
    
    smolagents v1.24 API:
      - `instructions` → injected into the system prompt template via {{custom_instructions}}
      - `step_callbacks` → called after each agent step for logging/monitoring
      - `max_steps` → forwarded to MultiStepAgent via **kwargs
    """
    settings = get_settings()
    
    # Configure Ollama through OpenAI compatible endpoint
    model = OpenAIServerModel(
        model_id=settings.ollama.model_name,
        api_base=f"{settings.ollama.base_url.rstrip('/')}/v1",
        api_key="ollama",  # dummy key for Ollama
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
        if session.config and isinstance(session.config, dict):
            mode = session.config.get("mode", "full")

        agent = create_agent(session_id=session_id, mode=mode)
        
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
