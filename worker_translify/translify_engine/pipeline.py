import os
import json
import time
import argparse
import logging
from pathlib import Path

try:
    from .phase1_extract import (
        extract_audio_gpu, separate_vocals_bgm, transcribe_whisper, run_paddle_ocr, clean_gpu_memory
    )
    from .phase2_translate import translate_pipeline_data
    from .phase3_compose import (
        generate_vietnamese_voiceover, clean_chinese_text_frames, assemble_final_video
    )
    from .subtitle_utils import segments_to_ass, segments_to_srt
except ImportError:
    from phase1_extract import (
        extract_audio_gpu, separate_vocals_bgm, transcribe_whisper, run_paddle_ocr, clean_gpu_memory
    )
    from phase2_translate import translate_pipeline_data
    from phase3_compose import (
        generate_vietnamese_voiceover, clean_chinese_text_frames, assemble_final_video
    )
    from subtitle_utils import segments_to_ass, segments_to_srt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("translify_pipeline")

class TranslifyPipeline:
    def __init__(self, use_iopaint: bool = True, voice_name: str = "vi-VN-NamMinhNeural"):
        self.use_iopaint = use_iopaint
        self.voice_name = voice_name
        
    def process(self, video_path: str, output_path: str, work_dir: str) -> str:
        start_time = time.time()
        logger.info(f"🚀 Starting Video Translify Pipeline for: {video_path}")
        logger.info(f"Workspace: {work_dir}")
        os.makedirs(work_dir, exist_ok=True)
        
        # ── PHASE 1: extraction & recognition ──
        logger.info("=== Phase 1: Extracting & Recognizing Content ===")
        
        # 1.1 GPU Audio Extraction
        audio_wav = extract_audio_gpu(video_path, work_dir)
        
        # 1.2 ONNX Vocal & Instrumental Separation
        vocal_wav, bgm_wav = separate_vocals_bgm(audio_wav, work_dir)
        
        # 1.3 Faster-Whisper ASR
        raw_segments = transcribe_whisper(vocal_wav)
        
        # 1.4 PaddleOCR hard text extraction
        ocr_results = run_paddle_ocr(video_path, work_dir)
        
        clean_gpu_memory()
        
        # ── PHASE 2: Translation ──
        logger.info("=== Phase 2: Translating to Vietnamese ===")
        vi_segments, vi_ocr = translate_pipeline_data(raw_segments, ocr_results)
        
        # Save transcription segments to workspace for debug
        with open(os.path.join(work_dir, "segments_vi.json"), "w", encoding="utf-8") as f:
            json.dump(vi_segments, f, ensure_ascii=False, indent=2)
            
        # ── PHASE 3: Composition & Assembly ──
        logger.info("=== Phase 3: Creating Vietnamese Video ===")
        
        # 3.1 Edge-TTS Co-stretched Voiceover
        voice_viet_wav = generate_vietnamese_voiceover(vi_segments, work_dir, voice_name=self.voice_name)
        
        # 3.2 Inpaint & Clean screen Chinese text
        clean_video = clean_chinese_text_frames(
            video_path, vi_ocr, work_dir, use_iopaint=self.use_iopaint
        )
        
        # 3.3 Create styled ASS subtitles
        subtitle_ass = os.path.join(work_dir, "subtitles.ass")
        segments_to_ass(vi_segments, subtitle_ass)
        segments_to_srt(vi_segments, os.path.join(work_dir, "subtitles.srt"))
        
        # 3.4 Assemble Final Video
        final_video = assemble_final_video(
            clean_video, voice_viet_wav, bgm_wav, subtitle_ass, output_path, work_dir
        )
        
        duration = time.time() - start_time
        logger.info(f"🎉 Pipeline finished successfully in {duration:.1f} seconds!")
        logger.info(f"Output saved to: {final_video}")
        return final_video

# CLI entrypoint removed here, handled by __main__.py

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
