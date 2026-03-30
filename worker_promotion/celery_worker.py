"""
Celery worker for Video Promotion jobs.
Uses shared worker_base for common infrastructure.
"""

import os
import logging
from typing import Dict, Any

from shared_core.worker_base import create_celery_app, execute_video_task
from shared_core.minio_utils import (
    download_file_from_minio, is_minio_path, get_object_name,
)

from video_generator import generate_video

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_promotion")


# ── Prepare Assets (promotion-specific) ──────────────────────────────────────

def download_promotion_assets(config_data: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """Download MinIO assets specific to promotion worker."""
    images_dir = os.path.join(work_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # config_data should contain a list of image URLs in "images"
    if "images" in config_data:
        items = config_data["images"]
        if isinstance(items, str):
            items = [items]
            
        local_images = []
        for i, img_url in enumerate(items):
            if is_minio_path(img_url):
                obj_name = get_object_name(img_url)
                # Keep file extension
                ext = os.path.splitext(obj_name)[1]
                local_path = os.path.join(images_dir, f"image_{i:03d}{ext}")
                download_file_from_minio(obj_name, local_path)
                local_images.append(local_path)
                
        # Update config to point to the local directory
        # The frontend/backend usually configures URLs; here we just use images_dir
        # Actually generate_video takes a list of image paths or a directory?
        # Let's see: `def generate_video(image_paths, output_path, config=None):` 
        # So we should pass the list of local images.
        config_data["local_images"] = local_images

    return config_data


# ── Build Function Adapters ──────────────────────────────────────────────────

def _build_promotion_video(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: call generate_video with the right signature."""
    local_images = local_config.get("local_images", [])
    output_mp4 = os.path.join(work_dir, "output.mp4")
    
    if not local_images:
        raise ValueError("No valid local images found for promotion video generator.")
        
    generate_video(local_images, output_mp4)
    return output_mp4


# ── Celery Tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="worker_promotion.tasks.process_video", bind=True, max_retries=2)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="promotion",
        prepare_fn=download_promotion_assets,
        build_fn=_build_promotion_video,
        change_cwd=False,
    )
