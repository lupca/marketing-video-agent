"""
Celery worker for Video Slideshow jobs.
Uses shared worker_base for common infrastructure.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

from shared_core.worker_base import create_celery_app, execute_video_task
from shared_core.minio_utils import (
    download_file_from_minio, is_minio_path, get_object_name,
)

from slideshow_engine.config import RenderContext, VARIANT_MAP
from slideshow_engine.pipeline import render_single_variant
from slideshow_engine.data_input import load_from_dict

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_slideshow")


# ── Prepare Assets (slideshow-specific) ────────────────────────────────────────

def download_slideshow_assets(config_data: Dict[str, Any], work_dir: str) -> Dict[str, Any]:
    """Download MinIO assets specific to slideshow worker and setup workspace."""
    images_dir = os.path.join(work_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    # Copy default assets (arrow) from worker source to work_dir
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for f in ["arrow.png"]:
        src = os.path.join(base_dir, f)
        dst = os.path.join(work_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            
    # Copy fonts
    fonts_dir = os.path.join(work_dir, "assets", "fonts")
    os.makedirs(fonts_dir, exist_ok=True)
    src_font = os.path.join(base_dir, "assets", "fonts", "BeVietnamPro-Bold.ttf")
    dst_font = os.path.join(fonts_dir, "BeVietnamPro-Bold.ttf")
    if os.path.exists(src_font):
        shutil.copy2(src_font, dst_font)

    # Download product images from MinIO
    if "input_json" in config_data and "products" in config_data["input_json"]:
        for product in config_data["input_json"]["products"]:
            image_url = product.get("image", "")
            if is_minio_path(image_url):
                obj_name = get_object_name(image_url)
                local_filename = os.path.basename(obj_name)
                local_path = os.path.join(images_dir, local_filename)
                download_file_from_minio(obj_name, local_path)
                # Update config to just use the local filename
                product["image"] = local_filename

    # Download required bg_music and logo
    if "assets" in config_data:
        assets = config_data["assets"]
        if "bg_music" in assets and is_minio_path(assets["bg_music"]):
            obj_name = get_object_name(assets["bg_music"])
            local_path = os.path.join(work_dir, "bg_music.mp3")
            download_file_from_minio(obj_name, local_path)
            
        if "logo" in assets and is_minio_path(assets["logo"]):
            obj_name = get_object_name(assets["logo"])
            local_path = os.path.join(work_dir, "logo.webp")
            download_file_from_minio(obj_name, local_path)

    return config_data


# ── Build Function Adapters ──────────────────────────────────────────────────

def _build_slideshow_video(local_config: Dict[str, Any], work_dir: str) -> str:
    """Adapter: call slideshow render pipeline with the right signature."""
    ctx = RenderContext(
        work_dir=Path(work_dir),
        images_dir=Path(work_dir) / "images",
        music_file=Path(work_dir) / "bg_music.mp3",
        blur_cache_dir=Path(work_dir) / ".cache_blur",
        tts_cache_dir=Path(work_dir) / ".cache_tts",
        font_path=Path(work_dir) / "assets" / "fonts" / "BeVietnamPro-Bold.ttf",
        logo_file=Path(work_dir) / "logo.webp",
        arrow_file=Path(work_dir) / "arrow.png",
        output_file=Path(work_dir) / "output.mp4"
    )
    
    variant_name = local_config.get("variant", "A")
    profile = VARIANT_MAP.get(variant_name, VARIANT_MAP["A"])
    
    # Parse video data
    content = load_from_dict(local_config.get("input_json", {}))
    
    output_path = render_single_variant(
        content=content,
        profile=profile,
        ctx=ctx
    )
    
    return str(output_path)


# ── Celery Tasks ─────────────────────────────────────────────────────────────

@celery_app.task(name="worker_slideshow.tasks.process_video", bind=True, max_retries=2)
def process_video(self, job_id: int, config_data: Dict[str, Any]):
    execute_video_task(
        job_id=job_id,
        config_data=config_data,
        job_type="slideshow",
        prepare_fn=download_slideshow_assets,
        build_fn=_build_slideshow_video,
        change_cwd=False,
    )
