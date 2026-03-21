import os
import sys
import logging
from moviepy.editor import VideoFileClip, concatenate_videoclips
from video_pipeline.effects import apply_warp_slide

logging.basicConfig(level=logging.INFO)

def main():
    clip1_path = "bk/1/1.mov"
    clip2_path = "bk/2/2.mov"
    out_path = "output/test_warp_slide.mp4"

    if not os.path.exists(clip1_path) or not os.path.exists(clip2_path):
        print("Missing test files in bk/ folder")
        sys.exit(1)

    # Load clips and fit them to 1080x1920 (or their original size if already 1080x1920)
    # We will just take the first 3 seconds of each to test
    clip1 = VideoFileClip(clip1_path).subclip(0, 3).resize((1080, 1920))
    clip2 = VideoFileClip(clip2_path).subclip(0, 3).resize((1080, 1920))

    # Apply warp slide to the end of clip1
    # Duration of transition: 0.5s
    clip1_warped = apply_warp_slide(
        clip1,
        direction="left",
        duration=0.5,
        intensity=40.0,
        frame_w=1080,
        frame_h=1920,
        max_blur_kernel=45
    )

    final = concatenate_videoclips([clip1_warped, clip2], method="compose")
    
    os.makedirs("output", exist_ok=True)
    print(f"Rendering test video to {out_path} ...")
    final.write_videofile(
        out_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        logger="bar"
    )
    print("Test video rendered successfully.")

if __name__ == "__main__":
    main()
