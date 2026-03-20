from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image
from moviepy.editor import ImageClip


LOGO_EXTS = (".png", ".webp", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".tif")


def find_logo_file(base_dir: Path) -> Optional[Path]:
    """Return the first image found inside logo/ directory, or None."""
    logo_dir = base_dir / "logo"
    if not logo_dir.is_dir():
        return None

    candidates = sorted(
        (f for f in logo_dir.iterdir() if f.is_file() and f.suffix.lower() in LOGO_EXTS),
        key=lambda p: (LOGO_EXTS.index(p.suffix.lower()), p.name),
    )
    return candidates[0] if candidates else None


def make_logo_overlay(
    base_dir: Path,
    assets: Dict,
    frame_w: int,
    frame_h: int,
    total_dur: float,
    logger,
) -> Optional[ImageClip]:
    """
    Build a full-frame transparent clip containing logo at configured position.

    Config path: assets.logo
      - width: target logo width in pixels (default 160)
      - x: left offset (default 48)
      - y: top offset (default 160)
      - opacity: 0.0..1.0 (default 0.90)
    """
    logo_cfg = assets.get("logo", {})
    logo_path = find_logo_file(base_dir)
    if logo_path is None:
        return None

    target_w = int(logo_cfg.get("width", 160))
    pos_x = int(logo_cfg.get("x", 48))
    pos_y = int(logo_cfg.get("y", 160))
    opacity = float(logo_cfg.get("opacity", 0.90))

    img = Image.open(str(logo_path)).convert("RGBA")
    orig_w, orig_h = img.size
    target_h = round(orig_h * target_w / orig_w)
    img = img.resize((target_w, target_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    canvas.paste(img, (pos_x, pos_y), img)

    logo_arr = np.array(canvas)
    rgb = logo_arr[:, :, :3]
    alpha = (logo_arr[:, :, 3].astype(float) / 255.0) * opacity

    clip = (
        ImageClip(rgb)
        .set_duration(total_dur)
        .set_mask(ImageClip(alpha, ismask=True).set_duration(total_dur))
    )
    logger.info(
        f"  Logo: {logo_path.name}  {target_w}x{target_h}px"
        f"  @ ({pos_x}, {pos_y})  opacity={opacity}"
    )
    return clip
