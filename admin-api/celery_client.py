"""
Celery client for the Admin API to dispatch tasks to workers.
"""

from celery import Celery
from shared_core.config import get_settings

_cfg = get_settings()

celery_app = Celery(
    "video_jobs",
    broker=_cfg.redis.url,
    backend=_cfg.redis.url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    # Route tasks to correct queues
    task_routes={
        "worker_review.tasks.*": {"queue": "review_queue"},
        "worker_unbox.tasks.*": {"queue": "unbox_queue"},
        "worker_download.tasks.*": {"queue": "download_queue"},
        "worker_slideshow.tasks.*": {"queue": "slideshow_queue"},
        "worker_promotion.tasks.*": {"queue": "promotion_queue"},
        "worker_agent.tasks.*": {"queue": "agent_queue"},
        "worker_research.tasks.*": {"queue": "research_queue"},
        "worker_text2img.tasks.*": {"queue": "text2img_queue"},
    },
)
