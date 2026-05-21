import os
import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)

from translify_engine.propainter_inpaint import inpaint_video_frames_propainter

def test_wrapper():
    print("Testing ProPainter wrapper module inpaint_video_frames_propainter...")
    
    # 1. Create a dummy sequence of 5 frames (BGR)
    frames = []
    masks = []
    
    for i in range(5):
        # A grey background frame
        frame = np.ones((240, 320, 3), dtype=np.uint8) * 128
        # Put a moving white text block in frame
        cv2.putText(frame, f"TEXT_{i}", (50 + i * 10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        
        # Binary mask covering the text area
        mask = np.zeros((240, 320), dtype=np.uint8)
        mask[50:150, 40:200] = 255
        
        frames.append(frame)
        masks.append(mask)
        
    work_dir = "./tmp_test_wrapper"
    os.makedirs(work_dir, exist_ok=True)
    
    try:
        # Run wrapper function
        out_frames = inpaint_video_frames_propainter(
            frames=frames,
            masks=masks,
            work_dir=work_dir,
            image_resize_ratio=1.0,
            mask_dilation=4
        )
        
        print("Success! Inpainted frame count:", len(out_frames))
        assert len(out_frames) == len(frames), f"Expected {len(frames)} frames but got {len(out_frames)}"
        assert out_frames[0].shape == frames[0].shape, f"Expected shape {frames[0].shape} but got {out_frames[0].shape}"
        
        # Verify the text was inpainted
        print("Checking first frame's center pixel (should be inpainted and not white/black):")
        # Center of masked area: y=100, x=100
        print("Center pixel BGR:", out_frames[0][100, 100])
        
    finally:
        # Cleanup
        if os.path.exists(work_dir):
            import shutil
            shutil.rmtree(work_dir)

if __name__ == "__main__":
    test_wrapper()
