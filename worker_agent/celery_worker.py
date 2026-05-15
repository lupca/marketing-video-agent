"""
Celery worker for Agent Orchestrator jobs.
"""

import logging

from shared_core.worker_base import create_celery_app
from worker_agent.agent_runner import run_agent_session_impl

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_agent", worker_type="agent")

@celery_app.task(name="worker_agent.tasks.run_agent_session", bind=True)
def run_agent_session(self, session_id: str):
    """
    Main entry point. Runs the agent orchestrator for a session.
    """
    logger.info(f"Worker Agent picked up session ID: {session_id}")
    run_agent_session_impl(session_id)
