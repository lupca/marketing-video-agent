"""Chat Assistant router — session management and real-time streaming completions."""

import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
from shared_core.llm_resolver import resolve_llm_config
import auth as auth_module

router = APIRouter(prefix="/api/chat", tags=["Chat Assistant"])


@router.post("/sessions", response_model=schemas.ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    session_in: schemas.ChatSessionCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Tạo một phiên hội thoại chat mới."""
    # Verify project existence
    project = db.query(models.Project).filter(models.Project.id == session_in.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
        
    new_session = models.ChatSession(
        project_id=session_in.project_id,
        user_id=current_user.id,
        title=session_in.title,
        selected_model_id=session_in.selected_model_id
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.get("/sessions", response_model=List[schemas.ChatSessionResponse])
def get_chat_sessions(
    project_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy toàn bộ các phiên hội thoại trong một Project."""
    sessions = db.query(models.ChatSession)\
        .filter(models.ChatSession.project_id == project_id)\
        .order_by(models.ChatSession.updated_at.desc())\
        .all()
    return sessions


@router.get("/sessions/{session_id}/messages", response_model=List[schemas.ChatMessageResponse])
def get_session_messages(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Lấy toàn bộ lịch sử tin nhắn của một phiên hội thoại."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    return session.messages


@router.post("/sessions/{session_id}/messages")
def submit_chat_message(
    session_id: str,
    message_in: schemas.ChatMessageCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """
    Gửi câu hỏi lên và nhận tin nhắn phản hồi dưới dạng Stream Server-Sent Events (SSE).
    Lưu cả câu hỏi và câu trả lời hoàn chỉnh vào Postgres DB một cách tự động.
    """
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    prompt_text = message_in.content.strip()
    if not prompt_text:
        raise HTTPException(status_code=400, detail="Message content cannot be empty.")
        
    # 1. Save user message immediately to Postgres DB
    user_msg = models.ChatMessage(
        session_id=session_id,
        sender="user",
        content=prompt_text
    )
    db.add(user_msg)
    db.commit()
    
    # 2. Fetch past conversation logs as history context (exclude the current user message)
    past_messages = db.query(models.ChatMessage)\
        .filter(models.ChatMessage.session_id == session_id, models.ChatMessage.id != user_msg.id)\
        .order_by(models.ChatMessage.created_at.asc())\
        .all()[-10:] # Limit to last 10 dialogues for LLM context
        
    # 3. Resolve base connection details for selected LLM model config
    config = resolve_llm_config(current_user.id, "chat_assistant")
    base_url = config["base_url"]
    model_name = config["model_name"]
    api_key = config["api_key"]

    # 4. Generator function for Streaming chunks
    def sse_generator():
        import requests
        
        api_url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        payload_messages = [{
            "role": "system",
            "content": "Bạn là một Trợ lý AI sáng tạo chuyên nghiệp tích hợp trong hệ sinh thái VidGenius. "
                       "Nhiệm vụ của bạn là hỗ trợ người dùng viết kịch bản video marketing (unbox, review...), "
                       "biên tập tiêu đề hấp dẫn, gợi ý prompts tạo ảnh nghệ thuật bằng FLUX AI, dịch thuật Việt-Anh siêu tốc, "
                       "và đưa ra các ý tưởng dựng video sáng tạo để giữ chân người xem. Phản hồi bằng tiếng Việt ngắn gọn, chuyên nghiệp, cấu trúc rõ ràng."
        }]
        
        for msg in past_messages:
            role = "user" if msg.sender == "user" else "assistant"
            payload_messages.append({"role": role, "content": msg.content})
            
        payload_messages.append({"role": "user", "content": prompt_text})
        
        req_payload = {
            "model": model_name,
            "messages": payload_messages,
            "temperature": 0.7,
            "stream": True
        }
        
        full_content = ""
        try:
            res = requests.post(api_url, json=req_payload, headers=headers, stream=True, timeout=60)
            res.raise_for_status()
            
            for line in res.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    data_part = line_str[6:]
                    if data_part == "[DONE]":
                        break
                    try:
                        chunk_json = json.loads(data_part)
                        delta = chunk_json["choices"][0]["delta"]
                        if "content" in delta:
                            token = delta["content"]
                            full_content += token
                            yield f"data: {json.dumps({'token': token})}\n\n"
                    except Exception:
                        pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
            
        # 5. Save final compiled AI response directly to database once completed
        if full_content:
            try:
                from shared_core.database import SessionLocal
                with SessionLocal() as db_gen:
                    new_ai_msg = models.ChatMessage(
                        session_id=session_id,
                        sender="assistant",
                        content=full_content
                    )
                    db_gen.add(new_ai_msg)
                    # Update the session updated_at time
                    db_gen.query(models.ChatSession)\
                        .filter(models.ChatSession.id == session_id)\
                        .update({models.ChatSession.updated_at: func.now()})
                    db_gen.commit()
            except Exception as ex:
                print(f"Error saving assistant message: {ex}")
                
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Xóa một phiên hội thoại chat."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    db.delete(session)
    db.commit()
    return {"status": "ok", "message": "Phiên hội thoại đã được xóa thành công."}


@router.put("/sessions/{session_id}", response_model=schemas.ChatSessionResponse)
def update_chat_session(
    session_id: str,
    session_update: schemas.ChatSessionUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cập nhật cấu hình phiên hội thoại chat (tên cuộc hội thoại hoặc model đã chọn)."""
    session = db.query(models.ChatSession).filter(models.ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
        
    if session_update.title is not None:
        session.title = session_update.title
    if session_update.selected_model_id is not None:
        session.selected_model_id = session_update.selected_model_id
        
    db.commit()
    db.refresh(session)
    return session
