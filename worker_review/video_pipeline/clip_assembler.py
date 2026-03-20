"""
video_pipeline/clip_assembler.py — File discovery, resize/crop, pacing, segment assembly.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

from moviepy.editor import VideoFileClip, concatenate_videoclips

from .effects import apply_slow_motion, extract_speed_factor

logger = logging.getLogger("VideoBuilder")


def _build_local_pacing_cycle(min_clip_duration: float, max_clip_duration: float) -> List[float]:
    """Build a deterministic long-short-long pacing cycle for one segment."""
    mn = max(0.1, float(min_clip_duration))
    mx = max(0.1, float(max_clip_duration))
    if mx < mn:
        mn, mx = mx, mn
    mid = (mn + mx) / 2.0
    return [mn, mid, mx, mid]


def get_sorted_video_files(
    folder_key: str,
    video_folders: Dict[str, str],
    base_dir: Path,
) -> List[Path]:
    """Return .mp4/.mov files in alpha-numeric order (recursive)."""
    folder = base_dir / video_folders[folder_key]
    if not folder.is_dir():
        raise FileNotFoundError(f"Video folder not found: {folder}")

    exts = {".mp4", ".mov"}
    files = sorted(
        (f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in exts),
        key=lambda p: p.name,
    )
    if not files:
        raise FileNotFoundError(f"No .mp4/.mov files in {folder}")

    logger.info(f"  Folder '{folder.name}/' → {len(files)} clip(s)")
    return files


def get_core_region(clip: VideoFileClip) -> Tuple[float, float]:
    """Return (core_start, core_end) after trimming 5% head + 5% tail."""
    d = clip.duration
    cs = d * 0.05
    ce = d * 0.95
    if ce - cs <= 0:
        return 0.0, d
    return cs, ce


def fit_frame(clip: VideoFileClip, width: int, height: int) -> VideoFileClip:
    """Scale & center-crop to target resolution. No distortion, no black bars."""
    tw, th = width, height
    cw, ch = clip.size
    target_ratio = tw / th

    if cw / ch > target_ratio:
        new_h = th
        new_w = int(cw * (th / ch))
    else:
        new_w = tw
        new_h = int(ch * (tw / cw))

    clip = clip.resize((new_w, new_h))
    x1 = (new_w - tw) // 2
    y1 = (new_h - th) // 2
    return clip.crop(x1=x1, y1=y1, x2=x1 + tw, y2=y1 + th)


def build_segment_clips(
    segment: Dict,
    video_folders: Dict[str, str],
    base_dir: Path,
    width: int,
    height: int,
    open_clips: List,
    default_pacing: Dict[str, float],
) -> VideoFileClip:
    """
    Build one timeline segment by:
    1. Listing raw clips in alpha-numeric order.
    2. Trimming 5% head + 5% tail of each raw clip ("core").
    3. Slicing the core sequentially into pacing-sized chunks.
    4. NO WRAPPING — once all files' cores are exhausted, stop.
    5. Resize + center-crop each chunk to target resolution.
    6. Concatenating available footage.
    7. Applying slow-motion if flagged.
    """
    start, end = segment["time_range"]
    seg_dur = end - start

    pacing_cfg = segment.get("pacing") or default_pacing or {}
    min_clip_duration = pacing_cfg.get("min_clip_duration", 1.2)
    max_clip_duration = pacing_cfg.get("max_clip_duration", 1.8)
    local_cycle = _build_local_pacing_cycle(min_clip_duration, max_clip_duration)

    speed = extract_speed_factor(segment)
    raw_needed = seg_dur * speed

    files = get_sorted_video_files(segment["video_source"], video_folders, base_dir)

    pieces: List[VideoFileClip] = []
    accumulated = 0.0
    fi = 0
    ci = 0
    cursor = None
    core_s = 0.0
    core_e = 0.0
    current_raw = None

    while accumulated < raw_needed - 0.05:
        remaining = raw_needed - accumulated
        if remaining < 0.1:
            break

        if cursor is None or cursor >= core_e - 0.05:
            if fi >= len(files):
                logger.info("    ⏹  All footage used — no repeat")
                break
            path = files[fi]
            fi += 1
            current_raw = VideoFileClip(str(path))
            open_clips.append(current_raw)
            core_s, core_e = get_core_region(current_raw)
            cursor = core_s

        target = local_cycle[ci % len(local_cycle)]
        ci += 1
        target = min(target, remaining)

        available = core_e - cursor
        if available < 0.3:
            cursor = core_e
            continue

        take = min(target, available)
        if take < 0.3 and remaining >= 0.3:
            cursor = core_e
            continue

        piece = current_raw.subclip(cursor, cursor + take)
        piece = fit_frame(piece, width, height)
        pieces.append(piece)

        cursor += take
        accumulated += piece.duration
        logger.info(
            f"    slice {len(pieces)}: "
            f"{cursor - take:.2f}-{cursor:.2f}s  "
            f"({piece.duration:.2f}s)"
        )

    if not pieces:
        raise RuntimeError(
            f"Could not generate clips for segment '{segment['segment']}'"
        )

    result = concatenate_videoclips(pieces, method="compose")
    result = apply_slow_motion(result, speed, logger)

    logger.info(f"  Segment actual duration: {result.duration:.2f}s (requested {seg_dur:.1f}s)")
    return result
