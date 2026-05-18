from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from shared_core import models, database
import auth as auth_module
import celery_client
import httpx
import os
import re

router = APIRouter(prefix="/api/translify", tags=["Translify"])

class RewriteRequest(BaseModel):
    zh_text: str
    original_text: str  # this is current vi_text
    duration: float
    tone: str  # "hào hứng", "bán hàng", etc.
    cta: Optional[str] = None

class ProjectUpdateRequest(BaseModel):
    project_data: Dict[str, Any]
    bgm: Optional[str] = None

@router.get("/projects/{job_id}")
def get_translify_project(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    # Retrieve job owned by current user
    job = (
        db.query(models.VideoJob)
        .join(models.Project)
        .filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Translify project job not found")
        
    if not job.config_data or "project_data" not in job.config_data:
        raise HTTPException(status_code=404, detail="Project analysis not ready or not found")
        
    # Return both the project_data and custom BGM if set in config_data
    return {
        "project_data": job.config_data["project_data"],
        "bgm": job.config_data.get("bgm")
    }

@router.put("/projects/{job_id}")
def update_translify_project(
    job_id: int,
    req: ProjectUpdateRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = (
        db.query(models.VideoJob)
        .join(models.Project)
        .filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Translify project job not found")
        
    # Update config_data
    cfg = dict(job.config_data) if job.config_data else {}
    cfg["project_data"] = req.project_data
    if req.bgm is not None:
        cfg["bgm"] = req.bgm
    job.config_data = cfg
    db.commit()
    return {"status": "success"}

@router.post("/projects/{job_id}/approve")
def approve_translify_project(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = (
        db.query(models.VideoJob)
        .join(models.Project)
        .filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Translify project job not found")
        
    # Set status back to PENDING so UI shows it's queuing/rendering
    job.status = "PENDING"
    db.commit()
    
    # Queue Stage 2 task
    try:
        celery_client.celery_app.send_task(
            "worker_translify.tasks.render_video",
            args=[job.id, job.config_data],
            queue="translify_queue",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue render task: {str(e)}")
        
    return {"status": "submitted"}

@router.post("/projects/{job_id}/reopen")
def reopen_translify_project(
    job_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    job = (
        db.query(models.VideoJob)
        .join(models.Project)
        .filter(models.VideoJob.id == job_id, models.Project.user_id == current_user.id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Translify project job not found")
        
    job.status = "WAITING_FOR_REVIEW"
    job.result_url = None
    job.error_message = None
    job.progress_percent = 100
    db.commit()
    return {"status": "reopened"}


@router.post("/tools/rewrite")
def rewrite_script(req: RewriteRequest):
    # LLM rewrite with custom tone & cta
    # Calculate word budget
    max_words = max(1, int(req.duration * 4.0)) # 4 words per second
    
    # Connect to Ollama
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    
    system_prompt = (
        "Bạn là một biên dịch viên video ngắn chuyên nghiệp.\n"
        "Yêu cầu:\n"
        f"1. Hãy dịch hoặc viết lại câu sau sang tiếng Việt mang tone giọng: '{req.tone}'"
    )
    if req.cta:
        system_prompt += f" và có thêm kêu gọi hành động (CTA): '{req.cta}'."
        
    system_prompt += (
        f"\n2. TỐI ĐA kịch bản chỉ được phép dài {max_words} từ/âm tiết để khớp thời lượng {req.duration} giây.\n"
        "3. Chỉ trả về duy nhất câu tiếng Việt mới đã rút gọn, TUYỆT ĐỐI không thêm giải thích, không có chữ Hán, không thêm ghi chú nào khác."
    )
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Câu gốc tiếng Trung (hoặc bản dịch nháp): {req.zh_text}\nBản dịch tiếng Việt hiện tại: {req.original_text}"}
        ],
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
            "num_predict": 64
        },
        "stream": False
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{ollama_url}/api/chat", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                rewritten = data["message"]["content"].strip()
                rewritten = re.sub(r'<think>.*?</think>', '', rewritten, flags=re.DOTALL).strip()
                rewritten = re.sub(r'[\u4e00-\u9fff]', '', rewritten)
                rewritten = rewritten.strip('"\'「」[]{}')
                return {"rewritten_text": rewritten}
    except Exception as e:
        # Fallback: return simple truncation of original text
        pass
        
    words = req.original_text.split()
    fallback = " ".join(words[:max_words])
    return {"rewritten_text": fallback}
