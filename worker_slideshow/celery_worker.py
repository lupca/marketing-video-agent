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
    is_downloadable_path, download_file_or_s3
)

from slideshow_engine.config import RenderContext, VARIANT_MAP
from slideshow_engine.pipeline import render_single_variant
from slideshow_engine.data_input import load_from_dict

logger = logging.getLogger(__name__)

celery_app = create_celery_app("worker_slideshow", worker_type="slideshow")


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

    # Deep copy to avoid mutating original
    import json
    config = json.loads(json.dumps(config_data))

    # Support unified Scene-Centric Schema
    if "scenes" in config:
        # Download bgm
        bgm_url = config.get("bgm_path") or config.get("audio", "")
        if bgm_url and is_downloadable_path(bgm_url):
            local_path = os.path.join(work_dir, "bg_music.mp3")
            download_file_or_s3(bgm_url, local_path)
            config["bgm_path"] = "bg_music.mp3"
            if "audio" in config:
                config["audio"] = "bg_music.mp3"

        # Download scene images
        for idx, s in enumerate(config.get("scenes", [])):
            image_url = s.get("clip_url", "")
            if image_url and is_downloadable_path(image_url):
                filename = os.path.basename(image_url.split("?")[0]) or f"image_{idx+1}.png"
                if not any(filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]):
                    filename = f"image_{idx+1}.png"
                local_path = os.path.join(images_dir, filename)
                download_file_or_s3(image_url, local_path)
                s["clip_url"] = filename

    # Support legacy schema
    else:
        # Download product images from MinIO
        if "input_json" in config and "products" in config["input_json"]:
            for product in config["input_json"]["products"]:
                image_url = product.get("image", "")
                if is_minio_path(image_url):
                    obj_name = get_object_name(image_url)
                    local_filename = os.path.basename(obj_name)
                    local_path = os.path.join(images_dir, local_filename)
                    download_file_from_minio(obj_name, local_path)
                    product["image"] = local_filename

        # Download required bg_music and logo
        if "assets" in config:
            assets = config["assets"]
            if "bg_music" in assets and is_minio_path(assets["bg_music"]):
                obj_name = get_object_name(assets["bg_music"])
                local_path = os.path.join(work_dir, "bg_music.mp3")
                download_file_from_minio(obj_name, local_path)
                
            if "logo" in assets and is_minio_path(assets["logo"]):
                obj_name = get_object_name(assets["logo"])
                local_path = os.path.join(work_dir, "logo.webp")
                download_file_from_minio(obj_name, local_path)

    return config


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
    # Parse video data - support scenes and input_json
    scenes = local_config.get("scenes", [])
    if scenes:
        # Dynamically map scenes to input_json style products
        products = []
        for idx, s in enumerate(scenes):
            products.append({
                "image": s.get("clip_url", ""),
                "text": s.get("text_overlay", ""),
                "hook": s.get("text_overlay", "")[:15] or "Khám phá ngay"
            })
        
        # Find first hook as intro and last text as outro
        intro_text = scenes[0].get("text_overlay", "Chào mừng")
        outro_text = scenes[-1].get("text_overlay", "Mua ngay tại giỏ hàng bên dưới!")
        
        slideshow_input = {
            "intro_text": intro_text,
            "outro_text": outro_text,
            "products": products
        }
        content = load_from_dict(slideshow_input)
    else:
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
