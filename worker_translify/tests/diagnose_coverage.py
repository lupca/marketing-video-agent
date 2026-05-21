"""
Diagnostic script to analyze text coverage gaps in the inpainting pipeline.
This will:
1. Load the project DB
2. For each scene, check tracking coverage gaps
3. Generate a detailed report of frames with text but no mask
"""
import os
import sys
import json
import cv2
import numpy as np
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from model.video_schema import VideoProject
from translify_engine.tracking_utils import get_tracked_polygons

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("diagnostics")

def analyze_scene_coverage(scene, original_video, work_dir, fps, width, height):
    """Analyze a single scene for text coverage gaps."""
    if not scene.visual.ocr_text:
        return None
    
    scene_dir = os.path.join(work_dir, scene.id)
    scene_raw_mp4 = os.path.join(scene_dir, "raw_clip.mp4")
    
    if not os.path.exists(scene_raw_mp4):
        return {"scene_id": scene.id, "error": "raw_clip.mp4 not found"}
    
    # Map OCR items
    ocr_results = []
    for item in scene.visual.ocr_text:
        ocr_results.append({
            "time_sec": getattr(item, 'time_sec', scene.start),
            "bbox": item.bbox,
            "text_zh": item.text_zh
        })
    
    # Get tracked polygons
    tracked_by_frame = get_tracked_polygons(scene_raw_mp4, ocr_results, fps, scene.start)
    
    # Count frames
    cap = cv2.VideoCapture(scene_raw_mp4)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    scene_dur = round(scene.end - scene.start, 2)
    
    # Find coverage statistics
    frames_with_mask = 0
    frames_without_mask = 0
    unique_ocr_times = set()
    for item in scene.visual.ocr_text:
        unique_ocr_times.add(item.time_sec)
    
    # Check tracking window
    window_frames = int(round(fps))
    
    # Compute which frames have mask
    covered_frames = set()
    uncovered_frames = set()
    for f_idx in range(total_frames):
        polys = tracked_by_frame.get(f_idx, [])
        has_mask = any(len(p) > 0 for p in polys) if polys else False
        if has_mask:
            covered_frames.add(f_idx)
        else:
            uncovered_frames.add(f_idx)
    
    # Find gaps between OCR detections
    ocr_frame_indices = []
    for item in scene.visual.ocr_text:
        f_detect = int(round((item.time_sec - scene.start) * fps))
        f_detect = max(0, min(total_frames - 1, f_detect))
        ocr_frame_indices.append(f_detect)
    
    ocr_frame_indices = sorted(set(ocr_frame_indices))
    
    # Compute max gap
    gaps = []
    if ocr_frame_indices:
        # Gap at the beginning
        if ocr_frame_indices[0] > window_frames:
            gaps.append(("start", 0, ocr_frame_indices[0] - window_frames))
        # Gaps between detections
        for i in range(len(ocr_frame_indices) - 1):
            gap_start = ocr_frame_indices[i] + window_frames
            gap_end = ocr_frame_indices[i + 1] - window_frames
            if gap_end > gap_start:
                gaps.append(("mid", gap_start, gap_end))
        # Gap at the end
        last_covered = ocr_frame_indices[-1] + window_frames
        if last_covered < total_frames:
            gaps.append(("end", last_covered, total_frames))
    
    return {
        "scene_id": scene.id,
        "time_range": f"{scene.start}s - {scene.end}s",
        "duration": scene_dur,
        "total_frames": total_frames,
        "ocr_items_count": len(scene.visual.ocr_text),
        "unique_ocr_timestamps": sorted(unique_ocr_times),
        "ocr_frame_indices": ocr_frame_indices,
        "tracking_window_frames": window_frames,
        "covered_frames": len(covered_frames),
        "uncovered_frames": len(uncovered_frames),
        "coverage_pct": round(len(covered_frames) / total_frames * 100, 1) if total_frames > 0 else 0,
        "coverage_gaps": gaps,
    }


if __name__ == "__main__":
    work_dir = "./translify_tmp"
    project_db_path = os.path.join(work_dir, "project_db.json")
    
    print("Loading project DB...")
    with open(project_db_path, "r", encoding="utf-8") as f:
        project_data = json.load(f)
    
    project = VideoProject.model_validate(project_data)
    
    # Get video metadata
    cap = cv2.VideoCapture("./atrox_88_china.mp4")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    print(f"Video: {width}x{height} @ {fps} FPS")
    print(f"Total scenes: {len(project.scenes)}")
    print("=" * 80)
    
    total_issues = 0
    
    for scene in project.scenes:
        result = analyze_scene_coverage(scene, "./atrox_88_china.mp4", work_dir, fps, width, height)
        if result is None:
            continue
        if "error" in result:
            print(f"\n[{result['scene_id']}] ERROR: {result['error']}")
            continue
        
        coverage = result["coverage_pct"]
        status = "✅" if coverage >= 95 else ("⚠️" if coverage >= 70 else "❌")
        
        print(f"\n{status} [{result['scene_id']}] {result['time_range']} ({result['duration']}s)")
        print(f"  Total frames: {result['total_frames']} | OCR items: {result['ocr_items_count']}")
        print(f"  OCR timestamps: {result['unique_ocr_timestamps']}")
        print(f"  OCR frame indices: {result['ocr_frame_indices']}")
        print(f"  Tracking window: ±{result['tracking_window_frames']} frames ({result['tracking_window_frames']/fps:.2f}s)")
        print(f"  Coverage: {result['covered_frames']}/{result['total_frames']} = {coverage}%")
        
        if result["coverage_gaps"]:
            print(f"  ⚠️ GAPS found:")
            for gap_type, gap_start, gap_end in result["coverage_gaps"]:
                gap_len = gap_end - gap_start
                gap_start_sec = round(gap_start / fps, 2)
                gap_end_sec = round(gap_end / fps, 2)
                print(f"    [{gap_type}] Frame {gap_start}-{gap_end} ({gap_len} frames, {gap_start_sec}s-{gap_end_sec}s)")
                total_issues += 1
    
    print("\n" + "=" * 80)
    print(f"Total coverage gap issues: {total_issues}")
