"""
video_pipeline/effects.py — Visual effects (snap zoom, camera shake, slow-motion, warp slide).
"""

from typing import Dict

import cv2
import numpy as np
from PIL import Image
from moviepy.editor import VideoFileClip, vfx


def extract_speed_factor(segment: Dict) -> float:
    """Parse ``slow_motion_<N>x`` from visual_effects.  Returns 1.0 if none."""
    for fx in segment.get("visual_effects", []):
        if isinstance(fx, str) and fx.startswith("slow_motion_"):
            return float(fx.split("_")[-1].replace("x", ""))
    return 1.0


# ═══════════════════════════════════════════════════════════════════════════
# Snap Zoom & Camera Shake
# ═══════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════
# Warp Slide — CapCut-style transition with mesh warp + motion blur
# ═══════════════════════════════════════════════════════════════════════════

def ease_in_out_cubic(t: float) -> float:
    """
    Cubic ease-in-out: chậm đầu, nhanh giữa, chậm cuối.
    Input/Output nằm trong [0, 1].
    """
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


def ease_velocity(t: float) -> float:
    """
    Đạo hàm của ease_in_out_cubic — biểu thị vận tốc tức thời.
    Chuẩn hóa về [0, 1] với peak ≈ 1.0 tại t=0.5.
    """
    if t < 0.5:
        v = 12.0 * t * t          # derivative of 4t³
    else:
        v = 12.0 * (1.0 - t) ** 2  # derivative of 1 - (-2t+2)³/2
    # Peak velocity = 3.0 at t=0.5 → normalize
    return min(v / 3.0, 1.0)


def build_warp_map(
    w: int,
    h: int,
    progress: float,
    direction: str = "left",
    intensity: float = 40.0,
) -> tuple:
    """
    Tạo bản đồ tọa độ (map_x, map_y) cho cv2.remap.

    Áp dụng biến dạng sinusoidal tại biên giới giữa 2 clip:
      x_new = x + intensity * sin(π * x / width) * warp_strength

    ``progress`` ∈ [0, 1]: tiến trình chuyển cảnh.
    ``warp_strength`` mạnh nhất ở giữa (progress ≈ 0.5), yếu ở 2 đầu.
    """
    # Warp strength: mạnh nhất ở giữa transition, dùng parabola
    warp_strength = 1.0 - (2.0 * progress - 1.0) ** 2  # peak=1 tại progress=0.5

    # Tạo grid tọa độ cơ sở
    map_x = np.zeros((h, w), dtype=np.float32)
    map_y = np.zeros((h, w), dtype=np.float32)

    # Tạo tọa độ nền
    x_coords = np.arange(w, dtype=np.float32)
    y_coords = np.arange(h, dtype=np.float32)
    base_x, base_y = np.meshgrid(x_coords, y_coords)

    if direction in ("left", "right"):
        # Biến dạng theo trục X: x_new = x + intensity * sin(π * x / w) * warp_strength
        displacement = intensity * np.sin(np.pi * base_x / w) * warp_strength
        if direction == "left":
            displacement = -displacement
        map_x = (base_x + displacement).astype(np.float32)
        # Thêm biến dạng Y nhẹ để tạo hiệu ứng "cong" tự nhiên
        y_wobble = intensity * 0.15 * np.sin(2.0 * np.pi * base_y / h) * warp_strength
        map_y = (base_y + y_wobble).astype(np.float32)
    else:
        # Biến dạng theo trục Y: y_new = y + intensity * sin(π * y / h) * warp_strength
        displacement = intensity * np.sin(np.pi * base_y / h) * warp_strength
        if direction == "up":
            displacement = -displacement
        map_y = (base_y + displacement).astype(np.float32)
        # Thêm biến dạng X nhẹ
        x_wobble = intensity * 0.15 * np.sin(2.0 * np.pi * base_x / w) * warp_strength
        map_x = (base_x + x_wobble).astype(np.float32)

    return map_x, map_y


def apply_directional_blur(
    frame: np.ndarray,
    velocity: float,
    direction: str = "left",
    max_kernel: int = 45,
) -> np.ndarray:
    """
    Motion blur hướng (ngang hoặc dọc).
    Kernel size = max_kernel * velocity  (velocity ∈ [0, 1]).
    Khi velocity cao → blur mạnh; velocity thấp → gần như không blur.
    """
    kernel_size = int(max_kernel * velocity)
    if kernel_size < 3:
        return frame

    # Đảm bảo kernel_size là lẻ
    if kernel_size % 2 == 0:
        kernel_size += 1

    if direction in ("left", "right"):
        # Kernel ngang
        kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
        kernel[kernel_size // 2, :] = 1.0 / kernel_size
    else:
        # Kernel dọc
        kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
        kernel[:, kernel_size // 2] = 1.0 / kernel_size

    return cv2.filter2D(frame, -1, kernel)


def apply_warp_slide(
    clip: VideoFileClip,
    direction: str = "left",
    duration: float = 0.5,
    intensity: float = 40.0,
    frame_w: int = 1080,
    frame_h: int = 1920,
    max_blur_kernel: int = 45,
) -> VideoFileClip:
    """
    Warp Slide: hiệu ứng slide biến dạng kiểu CapCut.

    Kết hợp 3 kỹ thuật:
    1. Cubic Easing (chuyển động mượt)
    2. Grid Mesh Warp (biến dạng lưới tọa độ tại biên giới)
    3. Dynamic Motion Blur (mờ hướng tỉ lệ vận tốc)

    Hiệu ứng áp dụng vào ``duration`` giây cuối của clip (khu vực chuyển cảnh).
    """
    clip_dur = clip.duration
    warp_start = max(0, clip_dur - duration)

    def _warp_slide(get_frame, t):
        frame = get_frame(t)

        # Chỉ áp dụng trong khoảng chuyển cảnh
        if t < warp_start:
            return frame

        # Progress: 0 → 1 trong khoảng [warp_start, clip_dur]
        if duration <= 0:
            return frame
        raw_progress = (t - warp_start) / duration
        raw_progress = max(0.0, min(1.0, raw_progress))

        # Eased progress cho slide position
        eased = ease_in_out_cubic(raw_progress)

        # Velocity cho motion blur
        velocity = ease_velocity(raw_progress)

        h, w = frame.shape[:2]

        # ── Bước 1: Tịnh tiến (slide) ────────────────────────────────
        # Đẩy frame ra ngoài theo hướng direction
        shifted = np.zeros_like(frame)
        if direction == "left":
            offset = int(eased * w)
            if offset < w:
                shifted[:, :w - offset] = frame[:, offset:]
        elif direction == "right":
            offset = int(eased * w)
            if offset < w:
                shifted[:, offset:] = frame[:, :w - offset]
        elif direction == "up":
            offset = int(eased * h)
            if offset < h:
                shifted[:h - offset, :] = frame[offset:, :]
        elif direction == "down":
            offset = int(eased * h)
            if offset < h:
                shifted[offset:, :] = frame[:h - offset, :]
        else:
            shifted = frame

        # ── Bước 2: Warp (biến dạng lưới) ───────────────────────────
        map_x, map_y = build_warp_map(w, h, raw_progress, direction, intensity)
        warped = cv2.remap(
            shifted,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

        # ── Bước 3: Motion blur ──────────────────────────────────────
        result = apply_directional_blur(warped, velocity, direction, max_blur_kernel)

        return result

    return clip.fl(_warp_slide)


# ═══════════════════════════════════════════════════════════════════════════
# Main effect dispatcher
# ═══════════════════════════════════════════════════════════════════════════

def apply_effects(
    clip: VideoFileClip,
    segment: Dict,
    seg_start: float,
    frame_w: int,
    frame_h: int,
    logger,
) -> VideoFileClip:
    """Apply non-speed visual effects (snap zoom, camera shake, warp slide, etc.) to a segment clip."""
    s_cfg = segment["time_range"][0]
    snap_zooms = []
    camera_shakes = []

    for fx in segment.get("visual_effects", []):
        # ── String shorthand: "warp_slide" ──
        if isinstance(fx, str) and fx == "warp_slide":
            clip = apply_warp_slide(
                clip,
                direction="left",
                duration=0.5,
                intensity=40.0,
                frame_w=frame_w,
                frame_h=frame_h,
            )
            logger.info("  Applied warp_slide (default: left, 0.5s)")
            continue

        if not isinstance(fx, dict):
            continue

        fx_type = fx.get("type")

        # ── Warp Slide (dict config) ──
        if fx_type == "warp_slide":
            ws_dir = fx.get("direction", "left")
            ws_dur = float(fx.get("duration", 0.5))
            ws_int = float(fx.get("intensity", 40.0))
            ws_blur = int(fx.get("max_blur_kernel", 45))
            clip = apply_warp_slide(
                clip,
                direction=ws_dir,
                duration=ws_dur,
                intensity=ws_int,
                frame_w=frame_w,
                frame_h=frame_h,
                max_blur_kernel=ws_blur,
            )
            logger.info(f"  Applied warp_slide dir={ws_dir} dur={ws_dur}s int={ws_int}")
            continue

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
