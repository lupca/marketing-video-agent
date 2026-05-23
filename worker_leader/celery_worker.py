"""
Celery worker for AI Leader Agent.
"""

import logging

from shared_core.worker_base import create_celery_app
from worker_leader.leader_runner import process_leader_job_impl

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_leader", worker_type="leader")

@celery_app.task(name="worker_leader.tasks.process_leader_job", bind=True)
def process_leader_job(self, job_id: int, config_data: dict = None):
    """
    Leader Agent task: analyzes script and creates a DRAFT job.
    """
    logger.info(f"Leader Agent picked up Job ID: {job_id}")
    process_leader_job_impl(job_id)
