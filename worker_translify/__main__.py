import argparse
import sys
import os

# Add root project path to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker_translify.translify_engine.pipeline import TranslifyPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Translify Pipeline CLI")
    parser.add_argument("--input", required=True, help="Path to input Chinese video")
    parser.add_argument("--output", required=True, help="Path to output Vietnamese video")
    parser.add_argument("--work-dir", default="./translify_tmp", help="Temp working directory")
    parser.add_argument("--no-iopaint", action="store_true", help="Disable IOPaint inpainting (fallback to opencv)")
    parser.add_argument("--voice", default="vi-VN-NamMinhNeural", help="Edge-TTS voice name")
    
    args = parser.parse_args()
    
    pipeline = TranslifyPipeline(use_iopaint=not args.no_iopaint, voice_name=args.voice)
    pipeline.process(args.input, args.output, args.work_dir)
