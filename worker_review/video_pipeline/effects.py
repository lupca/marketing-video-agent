"""
video_pipeline/effects.py — Visual effects (snap zoom, camera shake, slow-motion detection).
"""

from typing import Dict

import numpy as np
from PIL import Image
from moviepy.editor import VideoFileClip, vfx


def extract_speed_factor(segment: Dict) -> float:
    """Parse ``slow_motion_<N>x`` from visual_effects.  Returns 1.0 if none."""
    for fx in segment.get("visual_effects", []):
        if isinstance(fx, str) and fx.startswith("slow_motion_"):
            return float(fx.split("_")[-1].replace("x", ""))
    return 1.0


def apply_snap_zoom(
    clip: VideoFileClip,
    trigger_at: float,
    seg_start: float,
    frame_w: int,
    frame_h: int,
    intensity: float = 1.3,
    snap_frames: int = 2,
) -> VideoFileClip:
    """
    Snap zoom: in 1-2 frames after ``trigger_at``, jump from scale 1.0 to
    ``intensity`` and then keep that scale to the end of the clip.
    """
    local_t = trigger_at - seg_start
    tw, th = frame_w, frame_h

    def _zoom(get_frame, t):
        frame = get_frame(t)
        fps = getattr(clip, "fps", None) or 30.0
        snap_window = max(1, int(snap_frames)) / fps

        if t < local_t:
            scale = 1.0
        elif t < local_t + snap_window:
            scale = intensity
        else:
            scale = intensity

        if scale <= 1.001:
            return frame

        h, w = frame.shape[:2]
        nw = int(w / scale)
        nh = int(h / scale)
        x0 = (w - nw) // 2
        y0 = (h - nh) // 2

        cropped = frame[y0 : y0 + nh, x0 : x0 + nw]
        img = Image.fromarray(cropped).resize((tw, th), Image.LANCZOS)
        return np.array(img)

    return clip.fl(_zoom)


def apply_zoom_in(
    clip: VideoFileClip,
    trigger_at: float,
    seg_start: float,
    frame_w: int,
    frame_h: int,
    duration: float = 1.5,
    max_zoom: float = 1.2,
) -> VideoFileClip:
    """Backward-compatible alias: old zoom_in now behaves as snap zoom."""
    _ = duration  # kept for API compatibility
    return apply_snap_zoom(
        clip=clip,
        trigger_at=trigger_at,
        seg_start=seg_start,
        frame_w=frame_w,
        frame_h=frame_h,
        intensity=max_zoom,
    )


def apply_dynamic_vfx(
    clip: VideoFileClip,
    snap_zooms,
    camera_shakes,
    frame_w: int,
    frame_h: int,
) -> VideoFileClip:
    """Apply snap zoom and camera shake in one pass to reduce quality loss."""
    tw, th = frame_w, frame_h
    fps = getattr(clip, "fps", None) or 30.0

    normalized_shakes = []
    for fx in camera_shakes:
        amp = abs(float(fx["amplitude"]))
        dur = max(0.0, float(fx["duration"]))
        start = float(fx["start"])
        end = start + dur

        scale_pad = max(
            1.05,
            1.0 + (2.0 * amp / max(1.0, tw)),
            1.0 + (2.0 * amp / max(1.0, th)),
        )
        normalized_shakes.append({
            "start": start,
            "end": end,
            "amplitude": amp,
            "scale_pad": scale_pad,
        })

    def _vfx(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]

        scale = 1.0
        for fx in snap_zooms:
            if t >= fx["trigger"]:
                scale = max(scale, float(fx["intensity"]))

        active_shake = None
        for fx in normalized_shakes:
            if fx["start"] <= t < fx["end"]:
                active_shake = fx
                scale = max(scale, fx["scale_pad"])
                break

        if scale <= 1.001:
            return frame

        ew = max(tw, int(round(w * scale)))
        eh = max(th, int(round(h * scale)))
        enlarged = np.array(Image.fromarray(frame).resize((ew, eh), Image.LANCZOS))

        x = (ew - tw) // 2
        y = (eh - th) // 2

        if active_shake is not None:
            frame_idx = int(round(t * fps))
            seed = (frame_idx * 73856093) ^ (int(active_shake["start"] * 1000) * 19349663)
            rng = np.random.default_rng(seed)
            amp = int(round(active_shake["amplitude"]))
            dx = int(rng.integers(-amp, amp + 1))
            dy = int(rng.integers(-amp, amp + 1))
            x = x - dx
            y = y - dy

        x = max(0, min(x, ew - tw))
        y = max(0, min(y, eh - th))

        return enlarged[y : y + th, x : x + tw]

    return clip.fl(_vfx)


def apply_effects(
    clip: VideoFileClip,
    segment: Dict,
    seg_start: float,
    frame_w: int,
    frame_h: int,
    logger,
) -> VideoFileClip:
    """Apply non-speed visual effects (snap zoom, camera shake, etc.) to a segment clip."""
    s_cfg = segment["time_range"][0]
    snap_zooms = []
    camera_shakes = []

    for fx in segment.get("visual_effects", []):
        if not isinstance(fx, dict):
            continue

        fx_type = fx.get("type")
        if fx_type in {"snap_zoom", "zoom_in"}:
            trigger_at = float(fx.get("trigger_at", s_cfg))
            local_trigger = trigger_at - s_cfg
            abs_trigger = seg_start + local_trigger
            snap_zooms.append({
                "trigger": local_trigger,
                "intensity": max(1.0, float(fx.get("intensity", fx.get("max_zoom", 1.3)))),
            })
            logger.info(f"  Applied snap_zoom @ t={abs_trigger:.2f}s")

        elif fx_type == "camera_shake":
            start_time = float(fx.get("start_time", s_cfg))
            duration = max(0.0, float(fx.get("duration", 0.3)))
            amplitude = abs(float(fx.get("amplitude", 15)))

            local_start = start_time - s_cfg
            abs_start = seg_start + local_start
            camera_shakes.append({
                "start": local_start,
                "duration": duration,
                "amplitude": amplitude,
            })
            logger.info(
                f"  Applied camera_shake @ t={abs_start:.2f}s for {duration:.2f}s amp={amplitude:.0f}px"
            )

    if snap_zooms or camera_shakes:
        clip = apply_dynamic_vfx(clip, snap_zooms, camera_shakes, frame_w, frame_h)

    return clip


def apply_slow_motion(clip: VideoFileClip, speed: float, logger) -> VideoFileClip:
    """Apply slow-motion speed factor to a clip."""
    if speed != 1.0:
        clip = clip.fx(vfx.speedx, speed)
        logger.info(f"  Applied slow_motion ({speed}x)")
    return clip
