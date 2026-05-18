import os
import json
import logging
from typing import List, Tuple, Dict, Any

from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

from model.video_schema import VideoProject, Scene, SpeakerData, AudioData, VisualData, BgmData, OcrItem
from translify_engine.phase1_extract import (
    extract_audio_gpu, separate_vocals_bgm, transcribe_whisper, run_paddle_ocr, clean_gpu_memory
)
from translify_engine.phase2_translate import translate_with_ollama

logger = logging.getLogger(__name__)

def detect_scenes(video_path: str) -> List[Tuple[float, float]]:
    """
    Detect logical scenes/cuts in the video using PySceneDetect.
    Returns a list of (start_sec, end_sec) tuples.
    """
    logger.info(f"Detecting scenes using PySceneDetect for: {video_path}")
    try:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=27.0))  # standard threshold
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()
        
        scenes = []
        for scene in scene_list:
            start_sec = round(scene[0].get_seconds(), 2)
            end_sec = round(scene[1].get_seconds(), 2)
            scenes.append((start_sec, end_sec))
            
        if not scenes:
            duration = round(video.duration.get_seconds(), 2)
            scenes.append((0.0, duration))
            
        logger.info(f"PySceneDetect found {len(scenes)} scenes.")
        return scenes
    except Exception as e:
        logger.error(f"Failed to detect scenes: {e}. Falling back to full video scene.")
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = round(frame_count / fps, 2)
        cap.release()
        return [(0.0, duration)]

class AnalysisEngine:
    def __init__(self, use_ollama: bool = True):
        self.use_ollama = use_ollama

    def analyze(self, video_path: str, work_dir: str, project_id: str = "project_1") -> VideoProject:
        """
        Analyze the full video, segment it, extract metadata, translate, and populate the VideoProject database.
        """
        logger.info("=== Starting Analysis Engine ===")
        os.makedirs(work_dir, exist_ok=True)
        
        # 1. Detect scenes
        scene_bounds = detect_scenes(video_path)
        
        # 2. Extract full video audio & transcribe (ASR)
        audio_wav = extract_audio_gpu(video_path, work_dir)
        vocal_wav, bgm_wav = separate_vocals_bgm(audio_wav, work_dir)
        
        # 2.1 Whisper Transcription
        whisper_segments = transcribe_whisper(vocal_wav)
        
        # 3. OCR Extraction
        ocr_results = run_paddle_ocr(video_path, work_dir)
        
        clean_gpu_memory()
        
        # 4. Map Whisper & OCR detections to each logical scene
        scenes_data: List[Scene] = []
        
        for idx, (start_sec, end_sec) in enumerate(scene_bounds):
            scene_id = f"scene_{idx + 1}"
            scene_dur = round(end_sec - start_sec, 2)
            
            # Map transcripts to scene
            # Find whisper segments where the midpoint falls inside the scene
            matching_transcripts = []
            for seg in whisper_segments:
                midpoint = (seg["start"] + seg["end"]) / 2
                if start_sec <= midpoint < end_sec:
                    matching_transcripts.append(seg["text"])
                    
            zh_text = " ".join(matching_transcripts).strip()
            
            # Map OCR results to scene
            matching_ocr: List[OcrItem] = []
            for res in ocr_results:
                t_sec = res["time_sec"]
                if start_sec <= t_sec < end_sec:
                    # Avoid duplicates
                    if not any(item.text_zh == res["text"] for item in matching_ocr):
                        matching_ocr.append(OcrItem(
                            bbox=res["bbox"],
                            text_zh=res["text"],
                            text_vi=None
                        ))
            
            # Translate Chinese texts to Vietnamese using Ollama
            vi_text = None
            if zh_text:
                logger.info(f"[{scene_id}] Translating transcript: '{zh_text}'")
                translated = translate_with_ollama([zh_text], prompt_type="subtitle")
                if translated:
                    vi_text = translated[0]
                    
            for item in matching_ocr:
                logger.info(f"[{scene_id}] Translating OCR title: '{item.text_zh}'")
                translated_ocr = translate_with_ollama([item.text_zh], prompt_type="ocr")
                if translated_ocr:
                    item.text_vi = translated_ocr[0]
            
            # Create Scene object
            scene_obj = Scene(
                id=scene_id,
                start=start_sec,
                end=end_sec,
                speaker=SpeakerData(id="A", face_bbox=[], emotion_src="neutral"),
                audio=AudioData(
                    zh_text=zh_text,
                    vi_text=vi_text,
                    duration=scene_dur,
                    tts_file=None,
                    emotion_target=None
                ),
                visual=VisualData(ocr_text=matching_ocr),
                bgm=BgmData(type="original", volume=0.5)
            )
            scenes_data.append(scene_obj)
            
        project = VideoProject(
            video_id=project_id,
            scenes=scenes_data
        )
        
        # Save project JSON DB to the workspace
        json_path = os.path.join(work_dir, "project_db.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))
            
        logger.info(f"Successfully generated initial Video-as-Data JSON DB at: {json_path}")
        return project
