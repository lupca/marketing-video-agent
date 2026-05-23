import argparse
import json
import logging
import os
import sys

# Ensure PYTHONPATH includes the current worker directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from translify_engine.phase1_extract import _separate_vocals_bgm_inprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args()

    try:
        vocal_wav, bgm_wav = _separate_vocals_bgm_inprocess(args.audio_path, args.work_dir)
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump({"vocal": vocal_wav, "bgm": bgm_wav}, f, ensure_ascii=False, indent=2)
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
