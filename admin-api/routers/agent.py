"""
Agent router — Manage automated Agent Orchestrator sessions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from shared_core import models, schemas, database
from celery_client import celery_app
import auth as auth_module

router = APIRouter(prefix="/api/agent", tags=["Agents"])


@router.post("/sessions", response_model=schemas.AgentSessionResponse)
def create_agent_session(
    session_data: schemas.AgentSessionCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    db_session = models.AgentSession(
        keyword=session_data.keyword,
        video_count=session_data.video_count,
        config=session_data.config,
        user_id=current_user.id,
        status="PENDING",
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    try:
        celery_app.send_task(
            "worker_agent.tasks.run_agent_session",
            args=[db_session.id],
            queue="agent_queue",
        )
    except Exception as e:
        db_session.status = "FAILED"
        db_session.summary = f"Failed to queue agent task: {str(e)}"
        db.commit()
        db.refresh(db_session)
        raise HTTPException(status_code=500, detail="Failed to queue agent task")

    return db_session


@router.get("/sessions", response_model=List[schemas.AgentSessionResponse])
def get_agent_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    return (
        db.query(models.AgentSession)
        .filter(models.AgentSession.user_id == current_user.id)
        .order_by(models.AgentSession.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/sessions/{session_id}", response_model=schemas.AgentSessionResponse)
def get_agent_session(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    session = (
        db.query(models.AgentSession)
        .filter(models.AgentSession.id == session_id, models.AgentSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return session


@router.get("/sessions/{session_id}/logs", response_model=List[schemas.AgentLogResponse])
def get_agent_logs(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    session = (
        db.query(models.AgentSession)
        .filter(models.AgentSession.id == session_id, models.AgentSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")

    return (
        db.query(models.AgentLog)
        .filter(models.AgentLog.session_id == session_id)
        .order_by(models.AgentLog.created_at.asc())
        .all()
    )


@router.post("/sessions/{session_id}/retry", response_model=schemas.AgentSessionResponse)
def retry_agent_session(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Re-dispatch a PENDING or FAILED agent session."""
    session = (
        db.query(models.AgentSession)
        .filter(models.AgentSession.id == session_id, models.AgentSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")

    if session.status not in ("PENDING", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry session with status '{session.status}'. Only PENDING or FAILED sessions can be retried.",
        )

    # Reset session state
    session.status = "PENDING"
    session.summary = None
    session.completed_at = None
    db.commit()

    # Clear old logs for a clean retry
    db.query(models.AgentLog).filter(models.AgentLog.session_id == session_id).delete()
    db.commit()

    try:
        celery_app.send_task(
            "worker_agent.tasks.run_agent_session",
            args=[session.id],
            queue="agent_queue",
        )
    except Exception as e:
        session.status = "FAILED"
        session.summary = f"Failed to re-queue agent task: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to re-queue agent task")

    db.refresh(session)
    return session


@router.post("/sessions/{session_id}/cancel", response_model=schemas.AgentSessionResponse)
def cancel_agent_session(
    session_id: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_module.get_current_user),
):
    """Cancel a PENDING or RUNNING agent session."""
    session = (
        db.query(models.AgentSession)
        .filter(models.AgentSession.id == session_id, models.AgentSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")

    if session.status not in ("PENDING", "RUNNING"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel session with status '{session.status}'. Only PENDING or RUNNING sessions can be cancelled.",
        )

    from datetime import datetime, timezone

    session.status = "CANCELLED"
    session.summary = "Cancelled by user."
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session
