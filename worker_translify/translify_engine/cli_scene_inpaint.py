import argparse
import json
import logging
import os
import sys

# Ensure PYTHONPATH includes the current worker directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.video_schema import Scene
from translify_engine.render_engine import _inpaint_scene_clip_inprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-mp4", required=True)
    parser.add_argument("--scene-data-json", required=True)
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-mp4", required=True)
    args = parser.parse_args()

    try:
        with open(args.scene_data_json, "r", encoding="utf-8") as f:
            scene_dict = json.load(f)
        scene_obj = Scene(**scene_dict)
        
        # Run inpaint_scene_clip_inprocess
        _inpaint_scene_clip_inprocess(
            scene_mp4=args.scene_mp4,
            scene=scene_obj,
            output_mp4=args.output_mp4,
            fps=args.fps,
            width=args.width,
            height=args.height,
            work_dir=args.work_dir
        )
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
