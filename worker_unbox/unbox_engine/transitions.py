"""
Transitions module for video engine.
Extracted from make_viral.py. Contains OpenCV-based transitions.
"""
from __future__ import annotations

import logging
from typing import Union

import cv2
import numpy as np
from PIL import Image

try:
    from rembg import remove as rembg_remove
    _HAS_REMBG = True
except ImportError:
    _HAS_REMBG = False

log = logging.getLogger(__name__)

class PopoutTransition:
    """AI-powered transition: extracts the foreground subject from Clip B
    and composites it over the tail of Clip A with a zoom-in pop-out effect
    and directional motion blur for a cinematic 'whip' feel.

    Requires ``rembg`` for background removal.  Falls back to a simple
    crossfade when rembg is not available.
    """

    def __init__(
        self,
        transition_frames: int = 10,
        scale_start: float = 0.80,
        scale_end: float = 1.00,
        blur_angle: float = 0.0,
        blur_kernel_max: int = 35,
        crossfade_weight_start: float = 0.0,
        crossfade_weight_end: float = 0.6,
    ) -> None:
        self.transition_frames = transition_frames
        self.scale_start = scale_start
        self.scale_end = scale_end
        self.blur_angle = blur_angle
        self.blur_kernel_max = blur_kernel_max
        self.crossfade_weight_start = crossfade_weight_start
        self.crossfade_weight_end = crossfade_weight_end

    @staticmethod
    def extract_foreground(frame_bgr: np.ndarray) -> np.ndarray:
        """Return BGRA image where the background is transparent."""
        if not _HAS_REMBG:
            raise RuntimeError("rembg is required for foreground extraction.")
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_in = Image.fromarray(rgb)
        pil_out = rembg_remove(pil_in)
        rgba = np.array(pil_out)
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        return bgra

    @staticmethod
    def apply_motion_blur(
        frame: np.ndarray, angle_deg: float = 0.0, kernel_size: int = 25,
    ) -> np.ndarray:
        """Apply a directional (linear) motion blur at *angle_deg*."""
        if kernel_size < 3:
            return frame
        ks = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
        kernel = np.zeros((ks, ks), dtype=np.float32)
        mid = ks // 2
        kernel[mid, :] = 1.0 / ks

        if abs(angle_deg) > 0.5:
            M = cv2.getRotationMatrix2D((mid, mid), angle_deg, 1.0)
            kernel = cv2.warpAffine(kernel, M, (ks, ks))
            s = kernel.sum()
            if s > 1e-6:
                kernel /= s

        return cv2.filter2D(frame, -1, kernel)

    @staticmethod
    def composite_fg_on_bg(
        bg_bgr: np.ndarray,
        fg_bgra: np.ndarray,
        scale: float = 1.0,
    ) -> np.ndarray:
        """Composite *fg_bgra* (with alpha) onto *bg_bgr* at centre,
        optionally scaled.
        """
        h_bg, w_bg = bg_bgr.shape[:2]
        h_fg, w_fg = fg_bgra.shape[:2]

        if abs(scale - 1.0) > 1e-4:
            new_w = int(w_fg * scale)
            new_h = int(h_fg * scale)
            fg_bgra = cv2.resize(fg_bgra, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            h_fg, w_fg = new_h, new_w

        x_off = (w_bg - w_fg) // 2
        y_off = (h_bg - h_fg) // 2

        fg_x1 = max(0, -x_off)
        fg_y1 = max(0, -y_off)
        fg_x2 = min(w_fg, w_bg - x_off)
        fg_y2 = min(h_fg, h_bg - y_off)
        bg_x1 = max(0, x_off)
        bg_y1 = max(0, y_off)
        bg_x2 = bg_x1 + (fg_x2 - fg_x1)
        bg_y2 = bg_y1 + (fg_y2 - fg_y1)

        if bg_x2 <= bg_x1 or bg_y2 <= bg_y1:
            return bg_bgr

        fg_patch = fg_bgra[fg_y1:fg_y2, fg_x1:fg_x2]
        alpha = fg_patch[:, :, 3:4].astype(np.float32) / 255.0
        fg_rgb = fg_patch[:, :, :3].astype(np.float32)

        result = bg_bgr.copy()
        bg_patch = result[bg_y1:bg_y2, bg_x1:bg_x2].astype(np.float32)
        blended = fg_rgb * alpha + bg_patch * (1.0 - alpha)
        result[bg_y1:bg_y2, bg_x1:bg_x2] = blended.astype(np.uint8)
        return result

    def build_transition(
        self,
        frames_a: list[np.ndarray],
        frames_b: list[np.ndarray],
    ) -> list[np.ndarray]:
        n = min(self.transition_frames, len(frames_a), len(frames_b))
        if n == 0:
            return []

        fg_bgra = self.extract_foreground(frames_b[0])
        log.info("PopoutTransition: foreground extracted (%dx%d)",
                 fg_bgra.shape[1], fg_bgra.shape[0])

        output: list[np.ndarray] = []
        for i in range(n):
            t = i / max(1, n - 1)
            bg = frames_a[len(frames_a) - n + i].copy()
            blur_strength = int(self.blur_kernel_max * (1.0 - t))
            if blur_strength >= 3:
                bg = self.apply_motion_blur(bg, self.blur_angle, blur_strength)

            cf_w = self.crossfade_weight_start + (
                self.crossfade_weight_end - self.crossfade_weight_start
            ) * t
            if cf_w > 0.01:
                b_frame = frames_b[i]
                if b_frame.shape[:2] != bg.shape[:2]:
                    b_frame = cv2.resize(b_frame, (bg.shape[1], bg.shape[0]))
                bg = cv2.addWeighted(bg, 1.0 - cf_w, b_frame, cf_w, 0)

            scale = self.scale_start + (self.scale_end - self.scale_start) * t
            frame = self.composite_fg_on_bg(bg, fg_bgra, scale=scale)
            output.append(frame)

        return output

    @staticmethod
    def crossfade_fallback(
        frames_a: list[np.ndarray],
        frames_b: list[np.ndarray],
        n: int = 10,
    ) -> list[np.ndarray]:
        n = min(n, len(frames_a), len(frames_b))
        if n == 0:
            return []
        out: list[np.ndarray] = []
        for i in range(n):
            t = i / max(1, n - 1)
            a = frames_a[len(frames_a) - n + i]
            b = frames_b[i]
            if a.shape[:2] != b.shape[:2]:
                b = cv2.resize(b, (a.shape[1], a.shape[0]))
            blended = cv2.addWeighted(a, 1.0 - t, b, t, 0)
            out.append(blended)
        return out


class LumaFadeTransition:
    """Transition that reveals Clip B through the dark→light luminance
    regions of Clip A.
    """

    def __init__(self, transition_frames: int = 12) -> None:
        self.transition_frames = transition_frames

    def build_transition(
        self,
        frames_a: list[np.ndarray],
        frames_b: list[np.ndarray],
    ) -> list[np.ndarray]:
        n = min(self.transition_frames, len(frames_a), len(frames_b))
        if n == 0:
            return []

        output: list[np.ndarray] = []
        for i in range(n):
            t = i / max(1, n - 1)
            a = frames_a[len(frames_a) - n + i]
            b = frames_b[i]
            if b.shape[:2] != a.shape[:2]:
                b = cv2.resize(b, (a.shape[1], a.shape[0]))

            gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
            thresh_val = int(t * 255)
            _, mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)

            blur_k = max(3, int(21 * (1.0 - abs(t - 0.5) * 2)))
            blur_k = blur_k if blur_k % 2 == 1 else blur_k + 1
            mask_soft = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)

            alpha = mask_soft.astype(np.float32)[:, :, np.newaxis] / 255.0
            blended = (a.astype(np.float32) * alpha +
                       b.astype(np.float32) * (1.0 - alpha))
            output.append(blended.astype(np.uint8))

        return output


class WhipPanTransition:
    """High-speed horizontal slide (whip pan) with heavy motion blur."""

    def __init__(
        self,
        transition_frames: int = 6,
        direction: int = 1,
        blur_kernel_max: int = 45,
    ) -> None:
        self.transition_frames = transition_frames
        self.direction = direction
        self.blur_kernel_max = blur_kernel_max

    def build_transition(
        self,
        frames_a: list[np.ndarray],
        frames_b: list[np.ndarray],
    ) -> list[np.ndarray]:
        n = min(self.transition_frames, len(frames_a), len(frames_b))
        if n == 0:
            return []

        output: list[np.ndarray] = []
        h, w = frames_a[0].shape[:2]

        for i in range(n):
            t = i / max(1, n - 1)
            a = frames_a[len(frames_a) - n + i]
            b = frames_b[i]
            if b.shape[:2] != a.shape[:2]:
                b = cv2.resize(b, (w, h))

            offset = int(t * w) * self.direction
            canvas = np.zeros_like(a)

            if self.direction > 0:
                a_x1_src = min(max(offset, 0), w)
                a_x2_src = w
                a_x1_dst = 0
                a_x2_dst = a_x2_src - a_x1_src

                b_x1_src = 0
                b_x2_src = min(offset, w)
                b_x1_dst = w - offset if offset <= w else 0
                b_x2_dst = w
            else:
                abs_off = abs(offset)
                a_x1_src = 0
                a_x2_src = max(w - abs_off, 0)
                a_x1_dst = abs_off
                a_x2_dst = w

                b_x1_src = max(w - abs_off, 0)
                b_x2_src = w
                b_x1_dst = 0
                b_x2_dst = min(abs_off, w)

            aw = a_x2_dst - a_x1_dst
            if aw > 0 and (a_x2_src - a_x1_src) > 0:
                src_w = min(a_x2_src - a_x1_src, aw)
                canvas[:, a_x1_dst:a_x1_dst + src_w] = a[:, a_x1_src:a_x1_src + src_w]

            bw = b_x2_dst - b_x1_dst
            if bw > 0 and (b_x2_src - b_x1_src) > 0:
                src_w = min(b_x2_src - b_x1_src, bw)
                canvas[:, b_x1_dst:b_x1_dst + src_w] = b[:, b_x1_src:b_x1_src + src_w]

            blur_t = 1.0 - abs(t - 0.5) * 2
            blur_k = int(self.blur_kernel_max * blur_t)
            if blur_k >= 3:
                blur_k = blur_k if blur_k % 2 == 1 else blur_k + 1
                kernel = np.zeros((blur_k, blur_k), dtype=np.float32)
                kernel[blur_k // 2, :] = 1.0 / blur_k
                canvas = cv2.filter2D(canvas, -1, kernel)

            output.append(canvas)

        return output


class AudioReactiveTransitionRouter:
    """Selects the optimal transition class based on the duration of the
    preceding clip (≈ distance to the next beat drop).
    """

    def __init__(self) -> None:
        self._whip_direction: int = 1

    def select(
        self, clip_a_duration: float,
    ) -> Union[LumaFadeTransition, PopoutTransition, WhipPanTransition]:
        if clip_a_duration >= 1.5:
            log.debug("Router: slow beat (%.2fs) → LumaFade", clip_a_duration)
            return LumaFadeTransition(transition_frames=12)

        if clip_a_duration >= 0.7:
            log.debug("Router: beat drop (%.2fs) → Popout", clip_a_duration)
            return PopoutTransition(
                transition_frames=10,
                scale_start=0.80,
                scale_end=1.00,
                blur_angle=0.0,
                blur_kernel_max=35,
            )

        direction = self._whip_direction
        self._whip_direction *= -1
        log.debug("Router: fast beat (%.2fs) → WhipPan dir=%d",
                  clip_a_duration, direction)
        return WhipPanTransition(
            transition_frames=6,
            direction=direction,
            blur_kernel_max=45,
        )
