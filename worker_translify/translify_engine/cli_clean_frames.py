import argparse
import json
import logging
import os
import sys

# Ensure PYTHONPATH includes the current worker directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translify_engine.phase3_compose import clean_chinese_text_frames

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--ocr-results-json", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-mp4", required=True)
    args = parser.parse_args()

    try:
        with open(args.ocr_results_json, "r", encoding="utf-8") as f:
            ocr_results = json.load(f)
        
        # Call clean_chinese_text_frames and write to temporary output
        # To avoid infinite recursion, we run this directly via the original InpaintConfig + TextInpainter clean_frames
        from translify_engine.phase3_compose import InpaintConfig, TextInpainter
        config = InpaintConfig()
        inpainter = TextInpainter(config)
        cleaned_temp = inpainter.clean_frames(args.video_path, ocr_results, args.work_dir)
        
        # Copy to the requested output path
        import shutil
        shutil.copy(cleaned_temp, args.output_mp4)
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
