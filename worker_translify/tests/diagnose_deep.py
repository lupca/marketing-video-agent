"""
Deep diagnostic: Extract frames from uncovered regions and run OCR to verify
if text actually exists there. Also test optical flow drift accuracy.
"""
import os, sys, json, cv2, numpy as np, logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
logging.basicConfig(level=logging.WARNING)

def check_text_in_uncovered_frames():
    """Extract uncovered frames and run PaddleOCR to check if text exists."""
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", device="cpu", enable_mkldnn=False,
                    ocr_version="PP-OCRv4", det_db_unclip_ratio=1.15, det_db_thresh=0.35, det_db_box_thresh=0.6)
    
    work_dir = "./translify_tmp"
    
    # Scenes with known coverage gaps
    gap_scenes = [
        {"id": "scene_9",  "gap_start_frame": 35, "gap_end_frame": 42,  "clip": f"{work_dir}/scene_9/raw_clip.mp4"},
        {"id": "scene_10", "gap_start_frame": 66, "gap_end_frame": 114, "clip": f"{work_dir}/scene_10/raw_clip.mp4"},
        {"id": "scene_20", "gap_start_frame": 102, "gap_end_frame": 116, "clip": f"{work_dir}/scene_20/raw_clip.mp4"},
    ]
    
    for scene_info in gap_scenes:
        clip = scene_info["clip"]
        if not os.path.exists(clip):
            print(f"\n❌ {scene_info['id']}: clip not found")
            continue
            
        cap = cv2.VideoCapture(clip)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"\n{'='*70}")
        print(f"🔍 {scene_info['id']} — Checking frames {scene_info['gap_start_frame']}→{scene_info['gap_end_frame']} (of {total} total)")
        print(f"{'='*70}")
        
        # Sample every 3rd frame in the gap to save time
        sample_frames = list(range(scene_info['gap_start_frame'], min(scene_info['gap_end_frame'], total), 3))
        # Always include last frame
        last = min(scene_info['gap_end_frame'] - 1, total - 1)
        if last not in sample_frames:
            sample_frames.append(last)
        
        text_found_count = 0
        for f_idx in sample_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Save frame temporarily
            tmp_path = f"/tmp/diag_frame_{scene_info['id']}_{f_idx}.jpg"
            cv2.imwrite(tmp_path, frame)
            
            # Run OCR
            result = ocr.ocr(tmp_path)
            texts_found = []
            if result and result[0]:
                res_obj = result[0]
                iterable_res = []
                if isinstance(res_obj, dict) or (hasattr(res_obj, "get") and "rec_texts" in res_obj):
                    texts = res_obj.get("rec_texts", [])
                    scores = res_obj.get("rec_scores", [])
                    polys = res_obj.get("dt_polys", [])
                    for t, s, p in zip(texts, scores, polys):
                        iterable_res.append((p, (t, s)))
                else:
                    iterable_res = res_obj
                    
                for line in iterable_res:
                    if not line or len(line) < 2 or not line[1] or len(line[1]) < 2:
                        continue
                    text = line[1][0]
                    conf = float(line[1][1])
                    bbox = line[0]
                    if conf > 0.5:  # Lower threshold to catch more
                        texts_found.append({"text": text, "conf": round(conf, 3), "bbox": [[round(p[0]), round(p[1])] for p in bbox]})
            
            if texts_found:
                text_found_count += 1
                print(f"  Frame {f_idx}: 🔴 TEXT FOUND ({len(texts_found)} items)")
                for t in texts_found:
                    print(f"    '{t['text']}' (conf={t['conf']}) bbox={t['bbox']}")
            else:
                print(f"  Frame {f_idx}: ✅ No text detected")
            
            os.remove(tmp_path)
        
        cap.release()
        
        if text_found_count > 0:
            print(f"\n  ⚠️ RESULT: {text_found_count}/{len(sample_frames)} sampled frames still have visible text!")
        else:
            print(f"\n  ✅ RESULT: No text found in any uncovered frame — text has likely disappeared")


def test_optical_flow_drift():
    """Test how much optical flow drifts over 2-3 seconds of tracking."""
    from translify_engine.tracking_utils import track_polygon_lk
    
    work_dir = "./translify_tmp"
    
    # Use scene_10 as the test case (longest gap)
    clip = f"{work_dir}/scene_10/raw_clip.mp4"
    if not os.path.exists(clip):
        print("\n❌ scene_10 clip not found for drift test")
        return
    
    cap = cv2.VideoCapture(clip)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Load all gray frames
    grays = []
    while True:
        ret, frame = cap.read()
        if not ret: break
        grays.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    cap.release()
    
    print(f"\n{'='*70}")
    print(f"🧪 Optical Flow Drift Test — scene_10 ({len(grays)} frames)")
    print(f"{'='*70}")
    
    # Load actual OCR bbox from project DB
    db = json.load(open(f"{work_dir}/project_db.json"))
    scene_10 = db['scenes'][9]
    
    # Pick the largest text bbox
    largest_ocr = max(scene_10['visual']['ocr_text'], 
                      key=lambda x: abs(x['bbox'][2][0]-x['bbox'][0][0]) * abs(x['bbox'][2][1]-x['bbox'][0][1]))
    
    poly_init = np.array(largest_ocr['bbox'], dtype=np.float32)
    f_start = int(round((largest_ocr['time_sec'] - scene_10['start']) * 30))
    f_start = max(0, min(len(grays)-1, f_start))
    
    print(f"  Starting polygon: {poly_init.tolist()}")
    print(f"  Text: '{largest_ocr['text_zh']}' at {largest_ocr['time_sec']}s (frame {f_start})")
    print(f"  Tracking forward {len(grays) - f_start - 1} frames...")
    
    # Track forward and record drift at key intervals
    poly_curr = poly_init.copy()
    for f in range(f_start, len(grays) - 1):
        poly_curr = track_polygon_lk(grays[f], grays[f+1], poly_curr)
        elapsed_frames = f - f_start + 1
        if elapsed_frames in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            drift = poly_curr - poly_init
            mean_drift = np.mean(np.abs(drift), axis=0)
            max_drift = np.max(np.abs(drift), axis=0)
            print(f"  After {elapsed_frames} frames ({elapsed_frames/30:.1f}s): mean_drift={mean_drift.round(1)}, max_drift={max_drift.round(1)}")
    
    final_drift = poly_curr - poly_init
    print(f"\n  FINAL after {len(grays)-f_start-1} frames ({(len(grays)-f_start-1)/30:.1f}s):")
    print(f"    Mean absolute drift: {np.mean(np.abs(final_drift), axis=0).round(1)} px")
    print(f"    Max absolute drift: {np.max(np.abs(final_drift), axis=0).round(1)} px")
    print(f"    Final polygon: {poly_curr.round(1).tolist()}")


if __name__ == "__main__":
    print("=" * 70)
    print("PHASE 1: Checking if text exists in uncovered frames")
    print("=" * 70)
    check_text_in_uncovered_frames()
    
    print("\n\n")
    print("=" * 70) 
    print("PHASE 2: Testing Optical Flow drift accuracy")
    print("=" * 70)
    test_optical_flow_drift()
