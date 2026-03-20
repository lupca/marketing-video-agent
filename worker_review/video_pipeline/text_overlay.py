"""
video_pipeline/text_overlay.py — Pillow-based text overlay fallback.
"""

import os
from typing import Dict, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, TextClip


def make_text_clip(
    text: str,
    duration: float,
    frame_w: int,
    frame_h: int,
    text_style: Dict,
) -> Optional[ImageClip]:
    """
    Yellow bold text with 3 px black stroke, centred on screen.
    First tries MoviePy TextClip (needs ImageMagick).
    Falls back to a pure-Pillow rendered clip if IM is unavailable.
    """
    fontsize = text_style.get("font_size", 80)
    color = text_style.get("color", "yellow")

    # Attempt 1: MoviePy TextClip (ImageMagick)
    try:
        tc = TextClip(
            text,
            fontsize=fontsize,
            color=color,
            font="Arial-Bold",
            stroke_color="black",
            stroke_width=3,
            method="caption",
            size=(frame_w - 100, None),
            align="center",
        )
        return tc.set_duration(duration).set_position("center")
    except Exception:
        pass

    # Attempt 2: Pure-Pillow fallback (no ImageMagick needed)
    try:
        img = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        font = None
        for name in [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]:
            if os.path.exists(name):
                font = ImageFont.truetype(name, fontsize)
                break
        if font is None:
            font = ImageFont.load_default()

        # Draw stroke (outline)
        stroke_w = 3
        for dx in range(-stroke_w, stroke_w + 1):
            for dy in range(-stroke_w, stroke_w + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.multiline_text(
                    (frame_w // 2 + dx, frame_h // 2 + dy),
                    text, font=font, fill="black",
                    anchor="mm", align="center",
                )
        # Draw foreground text
        draw.multiline_text(
            (frame_w // 2, frame_h // 2),
            text, font=font, fill=color,
            anchor="mm", align="center",
        )

        arr = np.array(img)
        tc = ImageClip(arr, ismask=False, transparent=True)
        return tc.set_duration(duration).set_position("center")
    except Exception:
        return None
