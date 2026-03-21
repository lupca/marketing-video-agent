"""
unbox_viral.py – Automated Viral Unbox Video Editor
=====================================================
Pipeline tự động edit video unbox ~20s đạt chuẩn viral TikTok/Reels.

Modules:
  1. AudioAnalyzer  – Beat detection (librosa) + Audio mixing (ASMR + BGM)
  2. VideoProcessor – YOLO smart crop 9:16, Optical-flow speed ramping
  3. Renderer       – FFmpeg h264_videotoolbox, transitions, text overlay

Usage:
    from unbox_viral import make_unbox_viral
    result = make_unbox_viral(work_dir=".", config={...})
"""
from __future__ import annotations

import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import librosa
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  Constants & Data Classes                                                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
TARGET_FPS = 30
TIKTOK_SAFE_TOP = 0.15       # 15% top margin
TIKTOK_SAFE_BOTTOM = 0.20    # 20% bottom margin
TIKTOK_SAFE_RIGHT = 0.15     # 15% right margin

# Motion analysis thresholds
STATIC_THRESHOLD = 2.0       # Below = static (cut)
REPETITIVE_THRESHOLD = 8.0   # Below = repetitive motion (speed ramp)
MOTION_WINDOW_SEC = 0.5      # Analysis window in seconds

# Speed ramp
SPEED_RAMP_FACTOR = 3.5      # Tua nhanh x3.5 cho cảnh lặp

# Crop tracking smoothing
EMA_ALPHA = 0.15             # Exponential moving average smoothing factor

# YOLO detection classes of interest (COCO dataset)
YOLO_INTEREST_CLASSES = {
    0,   # person
    26,  # handbag
    28,  # suitcase
    39,  # bottle
    41,  # cup
    56,  # chair
    63,  # laptop
    67,  # cell phone
    73,  # book
    76,  # scissors
}


class UnboxViralError(RuntimeError):
    """Base exception for unbox_viral pipeline."""
    pass


@dataclass(frozen=True)
class BeatInfo:
    """A single beat drop timestamp."""
    time: float
    strength: float = 1.0


@dataclass
class SegmentInfo:
    """Motion analysis result for a video segment."""
    start: float
    end: float
    motion_score: float
    classification: str  # "STATIC", "REPETITIVE", "DYNAMIC"


@dataclass
class CropRegion:
    """Crop coordinates for a single frame in 9:16 output."""
    cx: int  # center x in source frame
    cy: int  # center y in source frame
    w: int   # crop width in source
    h: int   # crop height in source


@dataclass
class ProcessedSegment:
    """A segment ready for rendering."""
    start: float
    end: float
    speed_factor: float  # 1.0 = normal, 3.5 = speed ramp
    is_beat_cut: bool    # True = hard cut at beat drop
    classification: str


@dataclass(frozen=True)
class TextEvent:
    """A text overlay event."""
    start: float
    text: str
    event_type: str  # "hook" or "feature"


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  1. AudioAnalyzer                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class AudioAnalyzer:
    """Beat detection (librosa) and audio mixing for viral unbox videos."""

    def __init__(self, sr: int = 22050, hop_length: int = 512):
        self.sr = sr
        self.hop_length = hop_length
        self._ffmpeg = shutil.which("ffmpeg")
        if not self._ffmpeg:
            raise UnboxViralError("ffmpeg not found in PATH")

    # ── Beat Detection ──────────────────────────────────────────────────────

    def detect_beats(
        self,
        audio_path: str | Path,
        *,
        min_gap_sec: float = 0.4,
        drop_quantile: float = 0.72,
    ) -> List[BeatInfo]:
        """Detect beat drops using librosa onset + low-frequency energy."""
        audio_file = Path(audio_path).resolve()
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        y, sr = librosa.load(str(audio_file), sr=self.sr, mono=True)
        if y.size == 0:
            return []

        # Percussive component for beat tracking
        _, y_perc = librosa.effects.hpss(y)
        onset_env = librosa.onset.onset_strength(
            y=y_perc, sr=sr, hop_length=self.hop_length
        )

        _, beat_frames = librosa.beat.beat_track(
            y=y_perc, sr=sr, hop_length=self.hop_length, units="frames"
        )
        if beat_frames.size == 0:
            return []

        # Low-frequency energy spikes (bass drops)
        mel = librosa.feature.melspectrogram(
            y=y, sr=sr, hop_length=self.hop_length, n_mels=96
        )
        low_band = np.mean(mel[:10, :], axis=0)
        low_delta = np.maximum(0.0, np.diff(low_band, prepend=low_band[0]))

        onset_n = self._normalize(onset_env)
        low_n = self._normalize(low_delta)
        score = 0.65 * onset_n + 0.35 * low_n

        threshold = float(np.quantile(score[beat_frames], drop_quantile))
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr, hop_length=self.hop_length
        )

        selected: List[BeatInfo] = []
        for frame, bt in zip(beat_frames, beat_times):
            if score[frame] < threshold:
                continue
            if selected and bt - selected[-1].time < min_gap_sec:
                continue
            selected.append(BeatInfo(
                time=round(float(bt), 3),
                strength=round(float(score[frame]), 3),
            ))

        return selected

    # ── Audio Extraction ────────────────────────────────────────────────────

    def extract_original_audio(
        self, video_path: str | Path, output_path: str | Path
    ) -> Path:
        """Extract audio track from source video."""
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        self._run_ffmpeg([
            "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "44100", "-ac", "2",
            str(out),
        ])
        return out

    # ── Audio Mixing ────────────────────────────────────────────────────────

    def mix_audio(
        self,
        original_audio: str | Path,
        mp3_audio: str | Path,
        first_beat_time: float,
        total_duration: float,
        output_path: str | Path,
    ) -> Path:
        """
        Mix original ASMR audio with background music.
        Before first_beat_time: ASMR 100% + BGM 20%
        After first_beat_time:  BGM 100% + ASMR 10%
        """
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        # Build complex audio filter
        # [0] = original audio, [1] = bgm mp3
        # Crossfade transition at beat drop point
        bt = max(0.1, first_beat_time)
        filter_complex = (
            # Original audio: full volume before beat, 10% after
            f"[0:a]volume='if(lt(t,{bt}),1.0,0.10)':eval=frame[orig];"
            # BGM: 20% before beat, 100% after
            f"[1:a]volume='if(lt(t,{bt}),0.20,1.0)':eval=frame[bgm];"
            # Mix together
            f"[orig][bgm]amix=inputs=2:duration=first:dropout_transition=0[out]"
        )
        self._run_ffmpeg([
            "-i", str(original_audio),
            "-i", str(mp3_audio),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", f"{total_duration:.3f}",
            "-ar", "44100", "-ac", "2",
            str(out),
        ])
        return out

    # ── Speed Ramp Audio ────────────────────────────────────────────────────

    def speed_ramp_audio(
        self,
        audio_path: str | Path,
        speed: float,
        output_path: str | Path,
    ) -> Path:
        """Speed up audio with pitch increase (comic effect)."""
        out = Path(output_path).resolve()
        # atempo only supports 0.5-100.0 range
        # For pitch-shifted chipmunk effect, we use asetrate + aresample
        new_rate = int(44100 * speed)
        self._run_ffmpeg([
            "-i", str(audio_path),
            "-af", f"asetrate={new_rate},aresample=44100",
            str(out),
        ])
        return out

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=np.float32)
        lo, hi = float(np.min(v)), float(np.max(v))
        return np.zeros_like(v) if hi - lo < 1e-8 else (v - lo) / (hi - lo)

    def _run_ffmpeg(self, args: List[str]) -> subprocess.CompletedProcess:
        cmd = [self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnboxViralError(
                f"FFmpeg failed: {' '.join(cmd)}\n{proc.stderr.strip()}"
            )
        return proc


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  2. VideoProcessor                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class VideoProcessor:
    """YOLO smart-crop tracking + Optical-flow motion analysis."""

    def __init__(
        self,
        yolo_model_name: str = "yolov8n.pt",
        static_threshold: float = STATIC_THRESHOLD,
        repetitive_threshold: float = REPETITIVE_THRESHOLD,
    ):
        self.static_threshold = static_threshold
        self.repetitive_threshold = repetitive_threshold

        # Lazy-load YOLO to avoid import overhead
        self._yolo = None
        self._yolo_model_name = yolo_model_name

    def _get_yolo(self):
        """Lazy-load YOLO model on first use."""
        if self._yolo is None:
            try:
                from ultralytics import YOLO
                self._yolo = YOLO(self._yolo_model_name)
                logger.info(f"Loaded YOLO model: {self._yolo_model_name}")
            except Exception as e:
                logger.warning(f"Failed to load YOLO: {e}. Will use fallback.")
                self._yolo = None
        return self._yolo

    # ── Motion Analysis (Optical Flow) ──────────────────────────────────────

    def analyze_motion(
        self,
        video_path: str | Path,
        window_sec: float = MOTION_WINDOW_SEC,
    ) -> List[SegmentInfo]:
        """
        Analyze motion using Farneback Optical Flow.
        Classifies segments as STATIC, REPETITIVE, or DYNAMIC.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise UnboxViralError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or TARGET_FPS
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        window_frames = max(1, int(window_sec * fps))

        # Sample every other frame for speed
        sample_step = 2
        prev_gray = None
        flow_scores: List[float] = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (320, 180))  # Downscale for speed

                if prev_gray is not None:
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None,
                        pyr_scale=0.5, levels=3, winsize=15,
                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
                    )
                    mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    score = float(np.mean(mag))
                    flow_scores.append(score)
                else:
                    flow_scores.append(0.0)

                prev_gray = gray

            frame_idx += 1

        cap.release()

        if not flow_scores:
            return []

        # Group flow scores into windows
        scores_per_window = max(1, window_frames // sample_step)
        segments: List[SegmentInfo] = []

        for i in range(0, len(flow_scores), scores_per_window):
            chunk = flow_scores[i : i + scores_per_window]
            avg_score = float(np.mean(chunk))
            std_score = float(np.std(chunk))

            start_time = (i * sample_step) / fps
            end_time = min(((i + len(chunk)) * sample_step) / fps,
                           total_frames / fps)

            # Classification logic
            if avg_score < self.static_threshold:
                classification = "STATIC"
            elif avg_score < self.repetitive_threshold and std_score < 1.5:
                # Low variance + moderate motion = repetitive
                classification = "REPETITIVE"
            else:
                classification = "DYNAMIC"

            segments.append(SegmentInfo(
                start=round(start_time, 3),
                end=round(end_time, 3),
                motion_score=round(avg_score, 3),
                classification=classification,
            ))

        # Merge adjacent segments with same classification
        merged = self._merge_segments(segments)
        return merged

    def _merge_segments(self, segments: List[SegmentInfo]) -> List[SegmentInfo]:
        """Merge adjacent segments with the same classification."""
        if not segments:
            return []

        merged: List[SegmentInfo] = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]
            if prev.classification == seg.classification:
                # Merge: extend end, average score
                avg = (prev.motion_score + seg.motion_score) / 2
                merged[-1] = SegmentInfo(
                    start=prev.start,
                    end=seg.end,
                    motion_score=round(avg, 3),
                    classification=prev.classification,
                )
            else:
                merged.append(seg)

        return merged

    # ── Smart Crop Tracking (YOLO + Fallback) ───────────────────────────────

    def compute_crop_track(
        self,
        video_path: str | Path,
        sample_interval: int = 5,
    ) -> List[CropRegion]:
        """
        Compute per-frame crop regions for 9:16 output.
        Uses YOLO detection with saliency/center-crop fallback.
        Smoothed with EMA to prevent jitter.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise UnboxViralError(f"Cannot open video: {video_path}")

        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Calculate crop dimensions in source resolution
        # Target aspect: 9:16
        target_aspect = 9 / 16
        src_aspect = src_w / src_h

        if src_aspect > target_aspect:
            # Source is wider: crop width
            crop_h = src_h
            crop_w = int(src_h * target_aspect)
        else:
            # Source is taller: crop height
            crop_w = src_w
            crop_h = int(src_w / target_aspect)

        center_cx = src_w // 2
        center_cy = src_h // 2

        yolo = self._get_yolo()

        # Saliency detector fallback
        try:
            saliency = cv2.saliency.StaticSaliencySpectralResidual_create()
        except AttributeError:
            saliency = None
            logger.warning("OpenCV saliency not available, using center-crop fallback")

        raw_regions: List[CropRegion] = []
        frame_idx = 0
        last_detection: Optional[CropRegion] = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                region = self._detect_crop_region(
                    frame, src_w, src_h, crop_w, crop_h,
                    center_cx, center_cy, yolo, saliency,
                )
                last_detection = region
            else:
                # Reuse last detection between samples
                region = last_detection or CropRegion(center_cx, center_cy, crop_w, crop_h)

            raw_regions.append(region)
            frame_idx += 1

        cap.release()

        # Smooth with EMA
        smoothed = self._smooth_crop_track(raw_regions, crop_w, crop_h, src_w, src_h)
        return smoothed

    def _detect_crop_region(
        self,
        frame: np.ndarray,
        src_w: int, src_h: int,
        crop_w: int, crop_h: int,
        center_cx: int, center_cy: int,
        yolo, saliency,
    ) -> CropRegion:
        """Detect optimal crop region for a single frame."""
        cx, cy = center_cx, center_cy

        # Try YOLO detection
        if yolo is not None:
            try:
                results = yolo.predict(
                    frame, conf=0.3, verbose=False,
                    classes=list(YOLO_INTEREST_CLASSES),
                )
                if results and len(results[0].boxes) > 0:
                    boxes = results[0].boxes
                    # Pick the largest detection box
                    areas = (boxes.xyxy[:, 2] - boxes.xyxy[:, 0]) * \
                            (boxes.xyxy[:, 3] - boxes.xyxy[:, 1])
                    best_idx = int(areas.argmax())
                    x1, y1, x2, y2 = boxes.xyxy[best_idx].cpu().numpy()
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    return CropRegion(cx, cy, crop_w, crop_h)
            except Exception as e:
                logger.debug(f"YOLO detection failed: {e}")

        # Fallback: Saliency map
        if saliency is not None:
            try:
                success, sal_map = saliency.computeSaliency(frame)
                if success:
                    sal_map = (sal_map * 255).astype(np.uint8)
                    sal_map = cv2.GaussianBlur(sal_map, (25, 25), 0)
                    _, _, _, max_loc = cv2.minMaxLoc(sal_map)
                    cx, cy = max_loc[0], max_loc[1]
                    return CropRegion(cx, cy, crop_w, crop_h)
            except Exception as e:
                logger.debug(f"Saliency fallback failed: {e}")

        # Final fallback: center crop
        return CropRegion(center_cx, center_cy, crop_w, crop_h)

    def _smooth_crop_track(
        self,
        regions: List[CropRegion],
        crop_w: int, crop_h: int,
        src_w: int, src_h: int,
    ) -> List[CropRegion]:
        """Apply EMA smoothing and clamp to frame bounds."""
        if not regions:
            return []

        smoothed: List[CropRegion] = []
        ema_cx = float(regions[0].cx)
        ema_cy = float(regions[0].cy)

        half_w = crop_w // 2
        half_h = crop_h // 2

        for r in regions:
            ema_cx = EMA_ALPHA * r.cx + (1 - EMA_ALPHA) * ema_cx
            ema_cy = EMA_ALPHA * r.cy + (1 - EMA_ALPHA) * ema_cy

            # Clamp to prevent crop going out of frame
            cx = int(np.clip(ema_cx, half_w, src_w - half_w))
            cy = int(np.clip(ema_cy, half_h, src_h - half_h))

            smoothed.append(CropRegion(cx, cy, crop_w, crop_h))

        return smoothed

    # ── Build Processed Segments ────────────────────────────────────────────

    def build_segments(
        self,
        motion_segments: List[SegmentInfo],
        beat_times: List[float],
        min_dynamic_sec: float = 0.3,
    ) -> List[ProcessedSegment]:
        """
        Build final segment list:
        - Remove STATIC segments
        - Speed ramp REPETITIVE segments
        - Sync with beat drops for hard cuts
        """
        processed: List[ProcessedSegment] = []
        beat_set = set(beat_times)

        for seg in motion_segments:
            if seg.classification == "STATIC":
                # Skip static segments (dead footage)
                logger.debug(f"Cutting static segment: {seg.start:.2f}-{seg.end:.2f}")
                continue

            duration = seg.end - seg.start
            if seg.classification == "DYNAMIC" and duration < min_dynamic_sec:
                continue

            speed = SPEED_RAMP_FACTOR if seg.classification == "REPETITIVE" else 1.0

            # Check if this segment aligns with a beat drop
            is_beat = any(
                seg.start <= bt <= seg.end for bt in beat_times
            )

            processed.append(ProcessedSegment(
                start=seg.start,
                end=seg.end,
                speed_factor=speed,
                is_beat_cut=is_beat,
                classification=seg.classification,
            ))

        return processed


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  3. Renderer                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

class Renderer:
    """FFmpeg-based renderer with h264_videotoolbox HW accel on macOS."""

    def __init__(
        self,
        width: int = TARGET_WIDTH,
        height: int = TARGET_HEIGHT,
        fps: int = TARGET_FPS,
        crf: int = 20,
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.crf = crf
        self._ffmpeg = shutil.which("ffmpeg")
        self._ffprobe = shutil.which("ffprobe")
        if not self._ffmpeg:
            raise UnboxViralError("ffmpeg not found in PATH")

        # Check for hardware encoder
        self._hw_encoder = self._detect_hw_encoder()

    def _detect_hw_encoder(self) -> str:
        """Detect available hardware encoder. Prefer videotoolbox on Mac."""
        try:
            proc = subprocess.run(
                [self._ffmpeg, "-hide_banner", "-encoders"],
                capture_output=True, text=True,
            )
            if "h264_videotoolbox" in proc.stdout:
                logger.info("Using h264_videotoolbox hardware encoder")
                return "h264_videotoolbox"
        except Exception:
            pass
        logger.info("Using libx264 software encoder")
        return "libx264"

    # ── Render Segment ──────────────────────────────────────────────────────

    def render_segment(
        self,
        video_path: str | Path,
        segment: ProcessedSegment,
        crop_regions: List[CropRegion],
        output_path: str | Path,
        src_fps: float = 30.0,
    ) -> Path:
        """
        Render a single segment with smart crop and optional speed ramp.
        Uses per-frame crop data for smooth tracking.
        """
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        start_frame = int(segment.start * src_fps)
        end_frame = int(segment.end * src_fps)
        duration = segment.end - segment.start

        # Get average crop for this segment (use middle frame's crop)
        if crop_regions:
            mid_frame = min(
                (start_frame + end_frame) // 2,
                len(crop_regions) - 1
            )
            # Average crop over segment for stability
            seg_crops = crop_regions[
                max(0, start_frame): min(end_frame, len(crop_regions))
            ]
            if seg_crops:
                avg_cx = int(np.mean([c.cx for c in seg_crops]))
                avg_cy = int(np.mean([c.cy for c in seg_crops]))
                crop_w = seg_crops[0].w
                crop_h = seg_crops[0].h
            else:
                c = crop_regions[min(mid_frame, len(crop_regions) - 1)]
                avg_cx, avg_cy, crop_w, crop_h = c.cx, c.cy, c.w, c.h
        else:
            # Fallback: center crop
            avg_cx, avg_cy = 960, 540  # Assume 1920x1080
            crop_w, crop_h = 607, 1080

        # Calculate top-left corner of crop
        x = max(0, avg_cx - crop_w // 2)
        y = max(0, avg_cy - crop_h // 2)

        # Build filter chain
        filters = []

        # Crop from source
        filters.append(f"crop={crop_w}:{crop_h}:{x}:{y}")

        # Scale to target resolution
        filters.append(f"scale={self.width}:{self.height}")

        # Speed ramp via setpts
        if segment.speed_factor > 1.0:
            pts_factor = 1.0 / segment.speed_factor
            filters.append(f"setpts={pts_factor:.4f}*PTS")

        # Set output fps
        filters.append(f"fps={self.fps}")

        vf = ",".join(filters)

        # Audio filter for speed ramp
        af_args = []
        if segment.speed_factor > 1.0:
            # Chain atempo filters (each max 2.0x)
            remaining = segment.speed_factor
            atempo_chain = []
            while remaining > 2.0:
                atempo_chain.append("atempo=2.0")
                remaining /= 2.0
            atempo_chain.append(f"atempo={remaining:.4f}")
            af_args = ["-af", ",".join(atempo_chain)]

        # Encoder args
        enc_args = self._get_encoder_args()

        cmd = [
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{segment.start:.3f}",
            "-t", f"{duration:.3f}",
            "-i", str(video_path),
            "-vf", vf,
            *af_args,
            *enc_args,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(out),
        ]

        self._run(cmd)
        return out

    # ── Beat Drop Transitions ───────────────────────────────────────────────

    def concat_with_transitions(
        self,
        segment_files: List[Path],
        segments: List[ProcessedSegment],
        beat_times: List[float],
        output_path: str | Path,
    ) -> Path:
        """
        Concatenate segments with hard cuts.
        Apply zoom-in (115%) at beat drop points.
        """
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        if not segment_files:
            raise UnboxViralError("No segment files to concatenate")

        if len(segment_files) == 1:
            shutil.copy2(segment_files[0], out)
            return out

        # Build filter complex for concat with zoom at beat cuts
        inputs = []
        for f in segment_files:
            inputs.extend(["-i", str(f)])

        n = len(segment_files)
        filter_parts = []
        concat_inputs = []

        for i in range(n):
            seg = segments[i] if i < len(segments) else None

            if seg and seg.is_beat_cut:
                # Zoom-in 115% effect for beat-synced segments
                filter_parts.append(
                    f"[{i}:v]zoompan=z='min(zoom+0.003,1.15)'"
                    f":x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
                    f":d=1:s={self.width}x{self.height}"
                    f":fps={self.fps}[v{i}]"
                )
                concat_inputs.append(f"[v{i}]")
            else:
                concat_inputs.append(f"[{i}:v]")

        # Concat all video streams
        concat_input_str = "".join(concat_inputs)
        filter_parts.append(
            f"{concat_input_str}concat=n={n}:v=1:a=0[vout]"
        )

        filter_complex = ";".join(filter_parts)

        enc_args = self._get_encoder_args()

        cmd = [
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            *enc_args,
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            "-movflags", "+faststart",
            "-an",
            str(out),
        ]

        self._run(cmd)
        return out

    # ── Text Overlay ────────────────────────────────────────────────────────

    def overlay_text(
        self,
        video_path: str | Path,
        text_events: List[TextEvent],
        output_path: str | Path,
        font_path: Optional[str | Path] = None,
        font_size_hook: int = 84,
        font_size_feature: int = 64,
    ) -> Path:
        """
        Overlay text with easing animations (ease-out-back / spring).
        Respects TikTok safe zone.
        Uses MoviePy + Pillow for reliable Vietnamese text rendering.
        """
        from moviepy.editor import (
            CompositeVideoClip, ImageClip, VideoFileClip,
        )

        out = Path(output_path).resolve()
        src = Path(video_path).resolve()
        font = self._resolve_font(font_path)

        base = VideoFileClip(str(src))
        overlays: list = []
        tmp_imgs: List[Path] = []
        tmp_dir = Path(tempfile.mkdtemp(prefix="unbox_text_"))

        try:
            for ev in text_events:
                if ev.event_type == "hook":
                    img = self._render_text_image(
                        ev.text, font, font_size_hook,
                        max_width=int(self.width * 0.70),
                        stroke_width=5,
                    )
                    p = tmp_dir / f"hook_{len(tmp_imgs):03d}.png"
                    img.save(str(p))
                    tmp_imgs.append(p)

                    clip = ImageClip(str(p), transparent=True)

                    # Hook: centered in safe zone, ease-out-back at 0s
                    # Safe zone Y: between 15% and 80% of height
                    safe_y = int(self.height * TIKTOK_SAFE_TOP)
                    safe_bottom = int(self.height * (1 - TIKTOK_SAFE_BOTTOM))
                    center_y = (safe_y + safe_bottom) // 2 - clip.h // 2
                    center_x = (self.width - clip.w) // 2

                    def hook_pos(t, cx=center_x, cy=center_y,
                                 cw=clip.w, ch=clip.h):
                        # ease-out-back spring animation
                        progress = min(t / 0.4, 1.0)  # 0.4s animation
                        ease = self._ease_out_back(progress)
                        # Scale from 0 to 1
                        scale = ease
                        # Translate from slightly above
                        y_offset = int((1 - scale) * -80)
                        return (cx, cy + y_offset)

                    overlays.append(
                        clip.set_start(0.0)
                            .set_duration(min(3.0, base.duration))
                            .set_position(hook_pos)
                    )
                    continue

                # Feature text
                start = max(0.0, ev.start)
                if start >= base.duration:
                    continue

                img = self._render_text_image(
                    ev.text, font, font_size_feature,
                    max_width=int(self.width * 0.70),
                    stroke_width=4,
                )
                p = tmp_dir / f"feat_{len(tmp_imgs):03d}.png"
                img.save(str(p))
                tmp_imgs.append(p)

                clip = ImageClip(str(p), transparent=True)
                dur = min(2.8, base.duration - start)

                # TikTok safe zone: center horizontally, place in middle area
                safe_top = int(self.height * TIKTOK_SAFE_TOP)
                safe_bottom = int(self.height * (1 - TIKTOK_SAFE_BOTTOM))
                safe_right = int(self.width * (1 - TIKTOK_SAFE_RIGHT))
                # Center within safe zone
                feat_x = max(0, (self.width - clip.w) // 2)
                feat_y = int((safe_top + safe_bottom) / 2 + 80)  # Slightly below center

                def feat_pos(t, sx=start, fx=feat_x, fy=feat_y,
                             cw=clip.w):
                    elapsed = t - sx
                    if elapsed < 0:
                        return (-cw - 80, fy)

                    # ease-out-back spring animation over 0.35s
                    progress = min(elapsed / 0.35, 1.0)
                    ease = self._ease_out_back(progress)

                    # Pop from scale 0 → 1 with overshoot
                    # Start from center, scale X position
                    target_x = fx
                    x = int(target_x + (1 - ease) * 60)
                    y_bounce = int(fy - (1 - ease) * 40)

                    return (x, y_bounce)

                overlays.append(
                    clip.set_start(start)
                        .set_duration(dur)
                        .set_position(feat_pos)
                )

            comp = CompositeVideoClip(
                [base, *overlays], size=base.size
            ).set_duration(base.duration)

            comp.write_videofile(
                str(out), fps=self.fps, codec="libx264",
                audio_codec="aac", preset="veryfast",
                ffmpeg_params=["-crf", str(self.crf),
                               "-movflags", "+faststart"],
                threads=max(1, (os.cpu_count() or 4) // 2),
                verbose=False, logger=None,
            )
        finally:
            for c in overlays:
                try:
                    c.close()
                except Exception:
                    pass
            base.close()
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return out

    # ── Final Mux ───────────────────────────────────────────────────────────

    def mux_final(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        """Mux final video with mixed audio track."""
        out = Path(output_path).resolve()
        dur = self._probe_duration(video_path)

        enc_args = self._get_encoder_args()

        self._run([
            self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video_path), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-t", f"{dur:.3f}",
            "-movflags", "+faststart",
            str(out),
        ])
        return out

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _ease_out_back(t: float, s: float = 1.70158) -> float:
        """
        ease-out-back easing: overshoot then settle.
        Creates a spring/bounce effect for text animation.
        """
        t = max(0.0, min(1.0, t))
        t_rev = t - 1.0
        return 1.0 + t_rev * t_rev * ((s + 1) * t_rev + s)

    def _get_encoder_args(self) -> List[str]:
        """Get encoder-specific FFmpeg arguments."""
        if self._hw_encoder == "h264_videotoolbox":
            return [
                "-c:v", "h264_videotoolbox",
                "-q:v", "65",  # Quality (lower = better, 1-100)
                "-profile:v", "high",
                "-level", "4.1",
            ]
        return [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(self.crf),
        ]

    def _probe_duration(self, video_path: str | Path) -> float:
        """Probe video/audio duration."""
        proc = subprocess.run([
            self._ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ], capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnboxViralError(f"ffprobe failed for {video_path}")
        return float(proc.stdout.strip())

    @staticmethod
    def _resolve_font(font_path: Optional[str | Path] = None) -> Path:
        """Find a Vietnamese-compatible font."""
        if font_path:
            p = Path(font_path).resolve()
            if p.exists():
                return p
        for c in [
            Path("assets/fonts/NotoSans-Regular.ttf").resolve(),
            Path("assets/fonts/NotoSans-Medium.ttf").resolve(),
            Path("assets/fonts/BeVietnamPro-Regular.ttf").resolve(),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/Library/Fonts/Arial Unicode.ttf"),
            Path("/System/Library/Fonts/Helvetica.ttc"),
        ]:
            if c.exists():
                return c
        raise FileNotFoundError("No Vietnamese font found. Provide font_path.")

    @staticmethod
    def _render_text_image(
        text: str,
        font_path: Path,
        font_size: int,
        max_width: int,
        stroke_width: int = 4,
    ) -> Image.Image:
        """Render text with stroke and drop shadow to a transparent PNG."""
        font = ImageFont.truetype(str(font_path), size=font_size)

        # Measure text
        tmp = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        draw = ImageDraw.Draw(tmp)
        lines = _wrap_text(draw, text, font, max_width)
        ml = "\n".join(lines)

        bb = draw.multiline_textbbox(
            (0, 0), ml, font=font, spacing=10, stroke_width=stroke_width
        )
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        pad = 20

        img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)

        # Drop shadow
        dr.multiline_text(
            (pad + 3, pad + 3), ml, font=font,
            fill=(0, 0, 0, 200), spacing=10,
            stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255),
            align="center",
        )
        # Main text
        dr.multiline_text(
            (pad, pad), ml, font=font,
            fill=(255, 255, 255, 255), spacing=10,
            stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255),
            align="center",
        )
        return img

    @staticmethod
    def _run(cmd: List[str]) -> subprocess.CompletedProcess:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnboxViralError(
                f"Command failed: {' '.join(cmd[:8])}...\n{proc.stderr.strip()[:500]}"
            )
        return proc


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  Helper Functions                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> List[str]:
    """Word-wrap text to fit within max_w pixels."""
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}"
        if draw.textlength(cand, font=font) <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _parse_text_events(
    events: List[Dict[str, Any]],
    beat_times: List[float],
) -> List[TextEvent]:
    """
    Parse text events from config. Auto-assign beat times for events
    with time=None.
    """
    parsed: List[TextEvent] = []
    beat_idx = 0

    for ev in events:
        text = str(ev.get("text", "")).strip()
        event_type = str(ev.get("type", ev.get("effect", "feature"))).lower()
        raw_time = ev.get("time")

        if not text:
            continue

        if event_type == "hook":
            parsed.append(TextEvent(start=0.0, text=text, event_type="hook"))
            continue

        # Auto-assign beat time if time is None
        if raw_time is None:
            # Skip first beat (usually used for hard cut)
            while beat_idx < len(beat_times):
                bt = beat_times[beat_idx]
                beat_idx += 1
                if bt > 1.0:  # Skip beats in first second
                    parsed.append(TextEvent(start=bt, text=text, event_type="feature"))
                    break
        else:
            parsed.append(TextEvent(
                start=float(raw_time), text=text, event_type=event_type
            ))

    return parsed


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  4. Master Pipeline                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def make_unbox_viral(
    work_dir: str = ".",
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    End-to-end viral unbox video pipeline.

    Config keys:
        video (str | list[str]): Path(s) to raw unbox video(s)
        audio (str): Path to trending MP3
        text_events (list[dict]): Text overlay events

    Returns:
        str: Path to final output video
    """
    config = config or {}
    t0 = time.time()

    work_path = Path(work_dir).resolve()
    input_dir = work_path / "input"
    output_dir = work_path / "output"
    tmp_dir = work_path / ".unbox_viral_tmp"
    output_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # ── Resolve inputs ──────────────────────────────────────────────────

    # Video(s) - support both single and list
    if config.get("video"):
        if isinstance(config["video"], list):
            video_paths = [Path(v).resolve() for v in config["video"]]
        else:
            video_paths = [Path(config["video"]).resolve()]
    elif config.get("clips"):
        video_paths = [Path(c).resolve() for c in config["clips"]]
    else:
        video_paths = sorted(input_dir.glob("*.mov")) + sorted(input_dir.glob("*.mp4"))

    if not video_paths:
        raise UnboxViralError("No input video(s) found")
    for vp in video_paths:
        if not vp.exists():
            raise FileNotFoundError(f"Video not found: {vp}")

    if config.get("audio"):
        audio_path = Path(config["audio"]).resolve()
    else:
        mp3s = list(input_dir.glob("*.mp3"))
        audio_path = mp3s[0] if mp3s else None

    if not audio_path or not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    raw_text_events = config.get("text_events", [])

    # Use first video as primary (for single unbox video workflow)
    primary_video = video_paths[0]

    logger.info("=" * 60)
    logger.info("[1/6] Analyzing beats from BGM...")
    logger.info("=" * 60)

    # ── Step 1: Beat Detection ──────────────────────────────────────────

    audio_analyzer = AudioAnalyzer()
    beat_infos = audio_analyzer.detect_beats(audio_path)
    beat_times = [b.time for b in beat_infos]
    logger.info(f"  → {len(beat_times)} beat drops detected")
    logger.info(f"  → First 10: {beat_times[:10]}")

    first_beat = beat_times[0] if beat_times else 3.0

    # ── Step 2: Extract Original Audio ──────────────────────────────────

    logger.info("\n" + "=" * 60)
    logger.info("[2/6] Extracting original audio (ASMR)...")
    logger.info("=" * 60)

    original_audio = tmp_dir / "original_audio.wav"
    audio_analyzer.extract_original_audio(primary_video, original_audio)

    # ── Step 3: Motion Analysis + Smart Crop ────────────────────────────

    logger.info("\n" + "=" * 60)
    logger.info("[3/6] Analyzing motion & computing smart crop track...")
    logger.info("=" * 60)

    processor = VideoProcessor()
    motion_segments = processor.analyze_motion(primary_video)
    logger.info(f"  → {len(motion_segments)} motion segments")
    for seg in motion_segments:
        logger.info(
            f"    {seg.start:.1f}-{seg.end:.1f}s "
            f"[{seg.classification}] score={seg.motion_score:.2f}"
        )

    crop_regions = processor.compute_crop_track(primary_video)
    logger.info(f"  → {len(crop_regions)} crop track frames computed")

    processed_segments = processor.build_segments(motion_segments, beat_times)
    logger.info(f"  → {len(processed_segments)} segments after filtering")

    if not processed_segments:
        raise UnboxViralError("No usable segments found after motion analysis")

    # ── Step 4: Render Segments ─────────────────────────────────────────

    logger.info("\n" + "=" * 60)
    logger.info("[4/6] Rendering segments (smart crop + speed ramp)...")
    logger.info("=" * 60)

    renderer = Renderer()
    src_fps = _probe_fps(primary_video)
    segment_files: List[Path] = []

    for i, seg in enumerate(processed_segments):
        seg_out = tmp_dir / f"segment_{i:04d}.mp4"
        logger.info(
            f"  Rendering segment {i}: {seg.start:.1f}-{seg.end:.1f}s "
            f"[{seg.classification}] speed={seg.speed_factor}x"
        )
        renderer.render_segment(
            primary_video, seg, crop_regions, seg_out, src_fps
        )
        segment_files.append(seg_out)

    # ── Step 5: Concat + Transitions + Text ─────────────────────────────

    logger.info("\n" + "=" * 60)
    logger.info("[5/6] Concatenating with transitions + text overlay...")
    logger.info("=" * 60)

    concat_out = tmp_dir / "concat_video.mp4"
    renderer.concat_with_transitions(
        segment_files, processed_segments, beat_times, concat_out
    )

    # Parse text events (auto-assign to beats)
    text_events = _parse_text_events(raw_text_events, beat_times)
    logger.info(f"  → {len(text_events)} text events")

    if text_events:
        text_out = tmp_dir / "text_video.mp4"
        renderer.overlay_text(concat_out, text_events, text_out)
        video_for_mux = text_out
    else:
        video_for_mux = concat_out

    # ── Step 6: Audio Mix + Final Mux ───────────────────────────────────

    logger.info("\n" + "=" * 60)
    logger.info("[6/6] Mixing audio + final render...")
    logger.info("=" * 60)

    video_duration = renderer._probe_duration(video_for_mux)
    mixed_audio = tmp_dir / "mixed_audio.wav"
    audio_analyzer.mix_audio(
        original_audio, audio_path, first_beat,
        video_duration, mixed_audio,
    )

    final_output = output_dir / "unbox_viral_final.mp4"
    renderer.mux_final(video_for_mux, mixed_audio, final_output)

    # ── Cleanup ─────────────────────────────────────────────────────────

    shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed = time.time() - t0
    logger.info("\n" + "=" * 60)
    logger.info("HOÀN TẤT!")
    logger.info("=" * 60)
    logger.info(f"  → Output  : {final_output}")
    logger.info(f"  → Videos  : {len(video_paths)} input(s)")
    logger.info(f"  → Beats   : {len(beat_times)} beat drops")
    logger.info(f"  → Segments: {len(processed_segments)} (after filtering)")
    logger.info(f"  → Duration: {video_duration:.1f}s")
    logger.info(f"  → Time    : {elapsed:.1f}s")

    return str(final_output)


def _probe_fps(video_path: str | Path) -> float:
    """Probe video FPS."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return float(TARGET_FPS)
    try:
        proc = subprocess.run([
            ffprobe, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ], capture_output=True, text=True)
        if proc.returncode == 0:
            rate = proc.stdout.strip()
            if "/" in rate:
                num, den = rate.split("/")
                return float(num) / float(den)
            return float(rate)
    except Exception:
        pass
    return float(TARGET_FPS)


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  CLI Entry Point                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    make_unbox_viral()
