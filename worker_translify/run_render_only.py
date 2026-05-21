import os
import sys
import json
import logging

# Add root project path to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.video_schema import VideoProject
from translify_engine.render_engine import RenderEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

if __name__ == "__main__":
    work_dir = "./translify_tmp"
    project_db_path = os.path.join(work_dir, "project_db.json")
    
    print("Loading project DB...")
    with open(project_db_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
        
    project = VideoProject.model_validate(project_data)
    
    print("🚀 Starting Scene-Based Render Engine (Render Only)...")
    render_engine = RenderEngine(voice_name="vi-VN-NamMinhNeural")
    render_engine.render(
        project=project,
        original_video="./atrox_88_china.mp4",
        work_dir=work_dir,
        output_path="./atrox_88_vietnam.mp4"
    )
    print("🎉 Rendering completed!")
