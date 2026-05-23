import cv2
import numpy as np
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def track_polygon_lk(gray_prev: np.ndarray, gray_next: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """
    Tracks a 4-point polygon from gray_prev to gray_next using Lucas-Kanade Optical Flow.
    Generates a grid of points inside the polygon, calculates their translation,
    and applies the median translation to the polygon corners.
    """
    h, w = gray_prev.shape
    
    # 1. Get bounding box of the polygon
    x_min = int(np.floor(np.min(poly[:, 0])))
    x_max = int(np.ceil(np.max(poly[:, 0])))
    y_min = int(np.floor(np.min(poly[:, 1])))
    y_max = int(np.ceil(np.max(poly[:, 1])))
    
    # 2. Sample a grid of tracking points inside the bounding box
    step_x = max(2, int((x_max - x_min) / 6))
    step_y = max(2, int((y_max - y_min) / 4))
    
    grid_x, grid_y = np.meshgrid(
        np.arange(max(0, x_min), min(w, x_max), step_x),
        np.arange(max(0, y_min), min(h, y_max), step_y)
    )
    pts = np.vstack([grid_x.ravel(), grid_y.ravel()]).T
    
    # 3. Filter points that are actually inside the exact polygon
    pts_in = []
    poly_int = poly.astype(np.int32)
    for p in pts:
        if cv2.pointPolygonTest(poly_int, (float(p[0]), float(p[1])), False) >= 0:
            pts_in.append(p)
            
    # Fallback to the 4 corner points if grid sampling has too few points
    if len(pts_in) < 4:
        pts_in = poly.copy()
    else:
        pts_in = np.array(pts_in, dtype=np.float32)
        
    # 4. Calculate Optical Flow (Lucas-Kanade)
    pts_next, status, err = cv2.calcOpticalFlowPyrLK(
        gray_prev, gray_next, pts_in.astype(np.float32), None,
        winSize=(15, 15), maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
    )
    
    if pts_next is not None and status is not None and np.sum(status) > 0:
        valid_idx = np.where(status.ravel() == 1)[0]
        if len(valid_idx) > 0:
            # Calculate translation vectors
            diffs = pts_next[valid_idx] - pts_in[valid_idx]
            # Use median to filter out tracking noise/outliers (L1 estimator)
            median_diff = np.median(diffs, axis=0)
            return poly + median_diff
            
    return poly

def get_tracked_polygons(video_path: str, ocr_results: List[Dict[str, Any]], fps: float, scene_start: float) -> Dict[int, List[List[List[float]]]]:
    """
    Precomputes the tracked bounding box polygons for every frame of a video clip.
    Uses Local Random Access to track OCR results forward and backward in a small window,
    completely preventing CPU RAM exhaustion.
    """
    logger.info(f"Pre-computing tracked polygons for video (Local Random Access): {video_path}")
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Failed to open video for tracking: {video_path}")
        return {}
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(f"Video has {total_frames} frames.")
    if total_frames == 0:
        cap.release()
        return {}
        
    # Initialize dictionary for storing polygons per frame index
    tracked_by_frame = {f: [] for f in range(total_frames)}
    
    # Number of frames in a 1-second window
    window_frames = int(round(fps))
    
    # Track each OCR result forward and backward
    for res in ocr_results:
        t_detect = res.get("time_sec", scene_start)
        bbox = res.get("bbox", [])
        if not bbox or len(bbox) < 3:
            continue
            
        f_detect = int(round((t_detect - scene_start) * fps))
        f_detect = max(0, min(total_frames - 1, f_detect))
        
        poly_init = np.array(bbox, dtype=np.float32)
        tracked_by_frame[f_detect].append(poly_init.tolist())
        
        # 1. Track forward from detection frame using sequential reads from f_detect
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_detect)
        ret, frame = cap.read()
        if ret:
            gray_prev = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            poly_curr = poly_init.copy()
            for f in range(f_detect, min(total_frames - 1, f_detect + window_frames)):
                ret, frame = cap.read()
                if not ret:
                    break
                gray_next = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                poly_curr = track_polygon_lk(gray_prev, gray_next, poly_curr)
                tracked_by_frame[f+1].append(poly_curr.tolist())
                gray_prev = gray_next

        # 2. Track backward from detection frame using a small localized buffer
        start_back = max(0, f_detect - window_frames)
        if f_detect > start_back:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_back)
            back_buffer = []
            for _ in range(start_back, f_detect + 1):
                ret, frame = cap.read()
                if not ret:
                    break
                back_buffer.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                
            if len(back_buffer) > 1:
                poly_curr = poly_init.copy()
                # back_buffer[-1] corresponds to f_detect, back_buffer[0] to start_back
                for i in range(len(back_buffer) - 1, 0, -1):
                    gray_prev_back = back_buffer[i]
                    gray_next_back = back_buffer[i-1]
                    poly_curr = track_polygon_lk(gray_prev_back, gray_next_back, poly_curr)
                    actual_f = start_back + i - 1
                    tracked_by_frame[actual_f].append(poly_curr.tolist())

    cap.release()
    return tracked_by_frame
