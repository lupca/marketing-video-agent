import argparse
import sys
import os

# Add root project path to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worker_translify.translify_engine.analysis_engine import AnalysisEngine
from worker_translify.translify_engine.render_engine import RenderEngine

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Video Translify Pipeline CLI (Scene-Based Video-as-Data)")
    parser.add_argument("--input", required=True, help="Path to input Chinese video")
    parser.add_argument("--output", required=True, help="Path to output Vietnamese video")
    parser.add_argument("--work-dir", default="./translify_tmp", help="Temp working directory")
    parser.add_argument("--voice", default="vi-VN-NamMinhNeural", help="Edge-TTS voice name")
    
    args = parser.parse_args()
    
    print("🚀 [CLI] Starting Video-as-Data Analysis Engine...")
    analysis_engine = AnalysisEngine()
    project = analysis_engine.analyze(
        video_path=args.input,
        work_dir=args.work_dir,
        project_id="cli_project"
    )
    
    print("🚀 [CLI] Starting Constraint-Aware Rewrite Engine...")
    from worker_translify.translify_engine.constraint_engine import ConstraintEngine
    constraint_engine = ConstraintEngine()
    project = constraint_engine.apply_constraints(
        project=project,
        work_dir=args.work_dir
    )
    
    print("🚀 [CLI] Starting Scene-Based Render Engine...")
    render_engine = RenderEngine(voice_name=args.voice)
    render_engine.render(
        project=project,
        original_video=args.input,
        work_dir=args.work_dir,
        output_path=args.output
    )
    print("🎉 Pipeline run complete!")

