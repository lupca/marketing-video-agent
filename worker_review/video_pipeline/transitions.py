"""
video_pipeline/transitions.py — Inter-segment transitions (flash, crossfade, slide).
"""

from typing import List

import numpy as np
from moviepy.editor import ImageClip, VideoFileClip
from moviepy.video.compositing.transitions import crossfadein, slide_in

# Cycle through these transition styles between segments
TRANSITION_DUR: float = 0.2
TRANSITION_STYLES: List[str] = [
    "flash",       # white flash — punchy, TikTok-viral
    "crossfade",   # smooth dissolve
    "slide_left",  # incoming clip slides in from right
    "flash",
    "crossfade",
    "slide_up",    # incoming clip slides up from bottom
]


def make_flash_clip(dur: float, width: int, height: int) -> ImageClip:
    """Create a white flash frame for ``dur`` seconds."""
    white = np.full((height, width, 3), 255, dtype=np.uint8)
    return ImageClip(white).set_duration(dur)


def apply_transition(clip: VideoFileClip, style: str, dur: float) -> VideoFileClip:
    """Apply an entrance transition to ``clip``."""
    if style == "crossfade":
        return crossfadein(clip, dur)
    elif style == "slide_left":
        return slide_in(clip, dur, "right")
    elif style == "slide_up":
        return slide_in(clip, dur, "bottom")
    # "flash" is handled by inserting a flash clip before this segment
    return clip
