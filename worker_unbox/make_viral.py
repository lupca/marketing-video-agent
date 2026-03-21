"""
make_viral.py – One-command viral video generator
===================================================
Gộp toàn bộ pipeline vào 1 file duy nhất:
  1. Beat-drop detection (librosa)
  2. Trim silence + beat-synced scene cutting + 9:16 center-crop
  3. TikTok audio muxing
  4. Dynamic text overlay (Hook + Feature slide-in)

Usage:
    python3 make_viral.py
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import librosa
import numpy as np
from moviepy.editor import CompositeVideoClip, ImageClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFont

# rembg is optional – fallback to plain xfade when unavailable
try:
    from rembg import remove as rembg_remove
    _HAS_REMBG = True
except ImportError:
    _HAS_REMBG = False

log = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIG – edit these to match your project                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝
# Global static events fallback
TEXT_EVENTS: list[dict[str, Any]] = [

    {"time": 0.0, "text": "VỢT CẦU LÔNG SIÊU ĐỈNH 🔥", "effect": "hook"},
    {"time": 3.2, "text": "Cuốn cán chính hãng", "effect": "feature"},
    {"time": 5.8, "text": "Khung carbon siêu nhẹ", "effect": "feature"},
    {"time": 8.4, "text": "Cân bằng hoàn hảo", "effect": "feature"},
]


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Exceptions                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class FFmpegNotFoundError(RuntimeError):
    pass


class VideoProcessingError(RuntimeError):
    pass


class OverlayError(RuntimeError):
    pass


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  Data classes                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝
@dataclass(frozen=True)
class SceneSpec:
    source: Path
    start: float
    duration: float
    order: int


@dataclass(frozen=True)
class VideoTrimInfo:
    source: Path
    duration: float
    trim_start: float
    trim_end: float


@dataclass(frozen=True)
class TextEvent:
    start: float
    text: str
    effect: str


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  1. Beat-drop detection  (librosa)                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def detect_beat_drops(
    mp3_path: str | Path,
    *,
    sr: int = 22050,
    hop_length: int = 512,
    min_gap_sec: float = 0.32,
    drop_quantile: float = 0.75,
) -> list[float]:
    audio_file = Path(mp3_path).expanduser().resolve()
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    y, sr = librosa.load(str(audio_file), sr=sr, mono=True)
    if y.size == 0:
        return []

    _, y_perc = librosa.effects.hpss(y)
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr, hop_length=hop_length)

    _, beat_frames = librosa.beat.beat_track(
        y=y_perc, sr=sr, hop_length=hop_length, units="frames",
    )
    if beat_frames.size == 0:
        return []

    mel = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=hop_length, n_mels=96)
    low_band = np.mean(mel[:10, :], axis=0)
    low_delta = np.maximum(0.0, np.diff(low_band, prepend=low_band[0]))

    onset_n = _normalize(onset_env)
    low_n = _normalize(low_delta)
    score = 0.65 * onset_n + 0.35 * low_n

    threshold = float(np.quantile(score[beat_frames], drop_quantile))
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length)

    selected: list[float] = []
    for frame, bt in zip(beat_frames, beat_times):
        if score[frame] < threshold:
            continue
        if selected and bt - selected[-1] < min_gap_sec:
            continue
        selected.append(float(bt))

    return [round(t, 3) for t in selected]


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    lo, hi = float(np.min(v)), float(np.max(v))
    return np.zeros_like(v) if hi - lo < 1e-8 else (v - lo) / (hi - lo)


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  2. VideoViralEngine  (trim + beat-sync + crop + mux)                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class VideoViralEngine:
    _SILENCE_START_RE = re.compile(r"silence_start:\s*(\d+(?:\.\d+)?)")
    _SILENCE_END_RE = re.compile(r"silence_end:\s*(\d+(?:\.\d+)?)")

    def __init__(
        self,
        input_videos: Sequence[str | Path],
        *,
        target_width: int = 1080,
        target_height: int = 1920,
        scene_min_seconds: float = 1.2,
        scene_max_seconds: float = 2.0,
        silence_db: float = -34.0,
        silence_min_seconds: float = 0.25,
        fps: int = 30,
        crf: int = 21,
        preset: str = "veryfast",
        workers: int | None = None,
        seed: int | None = None,
        working_dir: str | Path = ".viral_engine_tmp",
        keep_temp: bool = False,
        beat_drop_times: Sequence[float] | None = None,
        audio_track: str | Path | None = None,
    ) -> None:
        if not input_videos:
            raise ValueError("input_videos must contain at least 1 file.")
        if scene_min_seconds <= 0 or scene_max_seconds <= 0:
            raise ValueError("scene durations must be > 0.")
        if scene_min_seconds > scene_max_seconds:
            raise ValueError("scene_min_seconds must be <= scene_max_seconds.")

        self.input_videos = [Path(v).expanduser().resolve() for v in input_videos]
        self.target_width = target_width
        self.target_height = target_height
        self.scene_min_seconds = scene_min_seconds
        self.scene_max_seconds = scene_max_seconds
        self.silence_db = silence_db
        self.silence_min_seconds = silence_min_seconds
        self.fps = fps
        self.crf = crf
        self.preset = preset
        self.keep_temp = keep_temp
        self.working_dir = Path(working_dir).expanduser().resolve()
        self.scene_dir = self.working_dir / "scenes"
        self.workers = workers or max(1, (os.cpu_count() or 4) // 2)
        self._rng = random.Random(seed)
        self.ffmpeg_bin = shutil.which("ffmpeg")
        self.ffprobe_bin = shutil.which("ffprobe")
        if not self.ffmpeg_bin or not self.ffprobe_bin:
            raise FFmpegNotFoundError("ffmpeg and ffprobe must be in PATH.")
        self.beat_drop_times = sorted(beat_drop_times) if beat_drop_times else None
        self.audio_track = Path(audio_track).expanduser().resolve() if audio_track else None
        if self.audio_track and not self.audio_track.exists():
            raise FileNotFoundError(f"Audio track not found: {self.audio_track}")
        missing = [str(p) for p in self.input_videos if not p.exists()]
        if missing:
            raise FileNotFoundError(f"Input files not found: {missing}")

    # ── public ──────────────────────────────────────────────────────────────
    def build(self, output_path: str | Path) -> Path:
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        self.scene_dir.mkdir(parents=True, exist_ok=True)

        trim_infos = self._analyze_inputs()
        scenes = self._build_scene_plan(trim_infos)
        if not scenes:
            raise VideoProcessingError("No scenes generated.")

        rendered = self._render_scenes(scenes)

        if self.audio_track:
            silent = self.working_dir / "concat_silent.mp4"
            self._concat_scenes(rendered, silent)
            self._mux_audio(silent, output)
        else:
            self._concat_scenes(rendered, output)

        if not self.keep_temp:
            shutil.rmtree(self.working_dir, ignore_errors=True)
        return output

    # ── ffmpeg helpers ──────────────────────────────────────────────────────
    def _run(self, cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise VideoProcessingError(
                f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
            )
        return proc

    def _probe_duration(self, video: Path) -> float:
        out = self._run([
            self.ffprobe_bin, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video),
        ]).stdout.strip()
        d = float(out)
        if d <= 0:
            raise VideoProcessingError(f"Invalid duration for {video}: {d}")
        return d

    # ── trim silence ────────────────────────────────────────────────────────
    def _detect_trim_bounds(self, video: Path, duration: float) -> tuple[float, float]:
        proc = subprocess.run(
            [self.ffmpeg_bin, "-hide_banner", "-i", str(video),
             "-af", f"silencedetect=noise={self.silence_db}dB:d={self.silence_min_seconds}",
             "-f", "null", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if proc.returncode != 0:
            return 0.0, duration

        segs: list[tuple[float, float]] = []
        active: float | None = None
        for line in proc.stderr.splitlines():
            m = self._SILENCE_START_RE.search(line)
            if m:
                active = float(m.group(1)); continue
            m = self._SILENCE_END_RE.search(line)
            if m and active is not None:
                segs.append((active, float(m.group(1)))); active = None
        if active is not None:
            segs.append((active, duration))

        ts, te = 0.0, duration
        if segs:
            if segs[0][0] <= 0.05:
                ts = max(0.0, segs[0][1])
            if segs[-1][1] >= duration - 0.05:
                te = min(duration, segs[-1][0])
        return (0.0, duration) if te - ts < 0.3 else (ts, te)

    def _analyze_one(self, video: Path) -> VideoTrimInfo:
        d = self._probe_duration(video)
        ts, te = self._detect_trim_bounds(video, d)
        return VideoTrimInfo(video, d, ts, te)

    def _analyze_inputs(self) -> list[VideoTrimInfo]:
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as ex:
            return list(ex.map(self._analyze_one, self.input_videos))

    # ── scene planning ──────────────────────────────────────────────────────
    def _build_scene_plan(self, infos: Iterable[VideoTrimInfo]) -> list[SceneSpec]:
        return (self._plan_beat_synced(infos) if self.beat_drop_times
                else self._plan_random(infos))

    def _plan_random(self, infos: Iterable[VideoTrimInfo]) -> list[SceneSpec]:
        scenes: list[SceneSpec] = []
        order = 0
        for info in infos:
            cursor, end = info.trim_start, info.trim_end
            while cursor < end:
                rem = end - cursor
                if rem < self.scene_min_seconds:
                    if scenes and scenes[-1].source == info.source:
                        p = scenes[-1]
                        scenes[-1] = SceneSpec(p.source, p.start, p.duration + rem, p.order)
                    elif rem >= 0.35:
                        scenes.append(SceneSpec(info.source, cursor, rem, order)); order += 1
                    break
                chunk = min(self._rng.uniform(self.scene_min_seconds, self.scene_max_seconds), rem)
                if 0 < rem - chunk < 0.35:
                    chunk = rem
                scenes.append(SceneSpec(info.source, cursor, chunk, order)); order += 1
                cursor += chunk
        return scenes

    def _plan_beat_synced(self, infos: Iterable[VideoTrimInfo]) -> list[SceneSpec]:
        pool = [(i.source, i.trim_start, i.trim_end) for i in infos]
        total = sum(e - s for _, s, e in pool)
        durs = self._beat_durations(list(self.beat_drop_times), total)

        scenes: list[SceneSpec] = []
        order = pi = 0
        pc = pool[0][1] if pool else 0.0
        for dur in durs:
            remaining = dur
            while remaining > 0 and pi < len(pool):
                src, _, ce = pool[pi]
                avail = ce - pc
                if avail <= 0:
                    pi += 1
                    if pi >= len(pool):
                        break
                    src, cs, ce = pool[pi]
                    pc = cs
                    avail = ce - pc
                chunk = min(remaining, avail)
                if chunk < 0.25:
                    pc += chunk
                    remaining -= chunk
                    if pc >= ce - 0.1:
                        pi += 1
                        if pi < len(pool):
                            pc = pool[pi][1]
                    continue
                scenes.append(SceneSpec(src, pc, chunk, order))
                order += 1
                pc += chunk
                remaining -= chunk
                if pc >= ce - 0.1:
                    pi += 1
                    if pi < len(pool):
                        pc = pool[pi][1]
        return scenes

    def _beat_durations(self, beats: list[float], total: float) -> list[float]:
        durs: list[float] = []
        cur = 0.0
        while cur < total - 1e-6:
            left = cur + self.scene_min_seconds
            right = min(cur + self.scene_max_seconds, total)
            if left >= total:
                r = total - cur
                if r >= 0.35: durs.append(round(r, 3))
                break
            win = [b for b in beats if left <= b <= right]
            if win:
                end = win[0]
            else:
                mid = (left + right) / 2.0
                near = self._nearest_beat(beats, mid)
                end = float(np.clip(near, left, right)) if near and abs(near - mid) <= 0.22 else right
            d = end - cur
            if d < 0.35: break
            durs.append(round(d, 3)); cur = end
            if total - cur < 0.35: break
        return durs

    @staticmethod
    def _nearest_beat(beats: list[float], target: float) -> float | None:
        if not beats: return None
        a = np.asarray(beats)
        return float(a[int(np.argmin(np.abs(a - target)))])

    # ── render + concat ─────────────────────────────────────────────────────
    def _render_scene(self, scene: SceneSpec, out: Path) -> None:
        # Scale & crop to 9:16, then Ken Burns zoom (center, ~10-15%)
        # zoompan d=1 = one output frame per input frame (video mode)
        vf = (
            f"scale={self.target_width}:{self.target_height}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={self.target_width}:{self.target_height},"
            f"zoompan=z='min(zoom+0.0015,1.15)'"
            f":x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
            f":d=1:s={self.target_width}x{self.target_height}"
            f":fps={self.fps}"
        )
        self._run([
            self.ffmpeg_bin, "-y",
            "-ss", f"{scene.start:.3f}", "-t", f"{scene.duration:.3f}",
            "-i", str(scene.source),
            "-map", "0:v:0",
            "-vf", vf,
            "-c:v", "libx264", "-preset", self.preset,
            "-crf", str(self.crf), "-pix_fmt", "yuv420p",
            "-an", "-threads", "0", str(out),
        ])

    def _render_scenes(self, scenes: Sequence[SceneSpec]) -> list[Path]:
        outs = [self.scene_dir / f"scene_{i:05d}.mp4" for i in range(len(scenes))]
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = [ex.submit(self._render_scene, s, o) for s, o in zip(scenes, outs)]
            for f in concurrent.futures.as_completed(futs):
                f.result()
        return outs

    def _concat_scenes(self, files: Sequence[Path], output: Path) -> None:
        if len(files) < 2:
            if files:
                shutil.copy2(files[0], output)
            return

        # ── Try audio-reactive AI transition ─────────────────────────────
        try:
            self._concat_with_smart_transitions(files, output)
            return
        except Exception as exc:
            log.warning("Smart transitions failed, falling back to xfade: %s", exc)

        # ── Fallback: original FFmpeg xfade ──────────────────────────────
        self._concat_with_xfade(files, output)

    # ── Audio-reactive transition concat (OpenCV frame-level) ───────────
    def _concat_with_smart_transitions(
        self, files: Sequence[Path], output: Path,
    ) -> None:
        """Decode scenes, pick the best transition per pair via
        AudioReactiveTransitionRouter, then re-encode."""
        router = AudioReactiveTransitionRouter()

        # Probe scene durations (seconds) for the router
        durations = [self._probe_duration(f) for f in files]

        # Decode all scenes into frame lists
        all_scene_frames: list[list[np.ndarray]] = []
        for f in files:
            frames = self._decode_video(f)
            if not frames:
                raise VideoProcessingError(f"Could not decode frames from {f}")
            all_scene_frames.append(frames)

        # Build final frame sequence with transitions baked in
        final_frames: list[np.ndarray] = []
        for idx, scene_frames in enumerate(all_scene_frames):
            if idx == 0:
                final_frames.extend(scene_frames)
                continue

            # Duration of the *previous* clip → determines beat intensity
            clip_a_dur = durations[idx - 1]
            transition = router.select(clip_a_dur)
            n_trans = transition.transition_frames
            log.info("Scene %d → %d: %s (dur=%.2fs, n=%d)",
                     idx - 1, idx, type(transition).__name__,
                     clip_a_dur, n_trans)

            prev_frames = all_scene_frames[idx - 1]
            cur_frames = scene_frames
            usable_n = min(n_trans, len(prev_frames), len(cur_frames))

            if usable_n >= 3:
                tail_a = prev_frames[-usable_n:]
                head_b = cur_frames[:usable_n]

                try:
                    trans_out = transition.build_transition(tail_a, head_b)
                except Exception as exc:
                    log.warning("Transition failed on scene %d (%s), "
                                "using crossfade fallback: %s",
                                idx, type(transition).__name__, exc)
                    trans_out = PopoutTransition.crossfade_fallback(
                        tail_a, head_b, usable_n,
                    )

                if trans_out:
                    final_frames[-usable_n:] = trans_out

                final_frames.extend(cur_frames[usable_n:])
            else:
                final_frames.extend(cur_frames)

        self._encode_frames(final_frames, output)

    def _decode_video(self, path: Path) -> list[np.ndarray]:
        """Read all frames from a video file via OpenCV."""
        cap = cv2.VideoCapture(str(path))
        frames: list[np.ndarray] = []
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame)
        finally:
            cap.release()
        return frames

    def _encode_frames(self, frames: list[np.ndarray], output: Path) -> None:
        """Write a list of BGR frames to an mp4 file via OpenCV."""
        if not frames:
            raise VideoProcessingError("No frames to encode.")
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        tmp_raw = self.working_dir / "_popout_raw.mp4"
        writer = cv2.VideoWriter(str(tmp_raw), fourcc, self.fps, (w, h))
        try:
            for f in frames:
                writer.write(f)
        finally:
            writer.release()

        # Re-encode with libx264 for proper compatibility & quality
        self._run([
            self.ffmpeg_bin, "-y",
            "-i", str(tmp_raw),
            "-c:v", "libx264", "-preset", self.preset,
            "-crf", str(self.crf), "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            "-movflags", "+faststart",
            "-an",
            str(output),
        ])
        tmp_raw.unlink(missing_ok=True)

    # ── Original xfade concat (FFmpeg filter_complex) ───────────────────
    def _concat_with_xfade(self, files: Sequence[Path], output: Path) -> None:
        xfade_duration = 0.5
        effects = ["fade", "slideleft"]

        durations = [self._probe_duration(f) for f in files]

        n = len(files)
        inputs: list[str] = []
        for f in files:
            inputs.extend(["-i", str(f)])

        filter_parts: list[str] = []
        offset = durations[0] - xfade_duration
        prev_label = "[0]"
        for i in range(1, n):
            effect = effects[i % len(effects)]
            out_label = f"[vx{i}]" if i < n - 1 else "[vout]"
            filter_parts.append(
                f"{prev_label}[{i}]xfade=transition={effect}"
                f":duration={xfade_duration}:offset={max(0, offset):.3f}{out_label}"
            )
            if i < n - 1:
                offset = offset + durations[i] - xfade_duration
            prev_label = out_label

        filter_complex = ";".join(filter_parts)

        self._run([
            self.ffmpeg_bin, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-c:v", "libx264", "-preset", self.preset,
            "-crf", str(self.crf), "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            "-movflags", "+faststart",
            "-an",
            str(output),
        ])

    def _mux_audio(self, video: Path, output: Path) -> None:
        dur = self._probe_duration(video)
        self._run([
            self.ffmpeg_bin, "-y",
            "-i", str(video), "-i", str(self.audio_track),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac",
            "-ar", "48000", "-ac", "2", "-b:a", "192k",
            "-t", f"{dur:.3f}", "-movflags", "+faststart", str(output),
        ])


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  2b. Foreground Pop-out & Optical Flow Whip Transition (OpenCV)        ║
# ╚══════════════════════════════════════════════════════════════════════════╝
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
        self.blur_angle = blur_angle  # degrees, 0 = horizontal whip
        self.blur_kernel_max = blur_kernel_max
        self.crossfade_weight_start = crossfade_weight_start
        self.crossfade_weight_end = crossfade_weight_end

    # ── foreground extraction ───────────────────────────────────────────
    @staticmethod
    def extract_foreground(frame_bgr: np.ndarray) -> np.ndarray:
        """Return BGRA image where the background is transparent."""
        if not _HAS_REMBG:
            raise RuntimeError("rembg is required for foreground extraction.")
        # rembg expects RGB PIL Image or raw bytes; easiest via PIL
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_in = Image.fromarray(rgb)
        pil_out = rembg_remove(pil_in)  # returns RGBA PIL Image
        rgba = np.array(pil_out)  # H×W×4, RGBA order
        # convert RGBA → BGRA for OpenCV consistency
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        return bgra

    # ── directional motion blur ─────────────────────────────────────────
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
        kernel[mid, :] = 1.0 / ks  # horizontal line kernel

        # rotate the kernel to the desired angle
        if abs(angle_deg) > 0.5:
            M = cv2.getRotationMatrix2D((mid, mid), angle_deg, 1.0)
            kernel = cv2.warpAffine(kernel, M, (ks, ks))
            s = kernel.sum()
            if s > 1e-6:
                kernel /= s

        return cv2.filter2D(frame, -1, kernel)

    # ── alpha compositing ───────────────────────────────────────────────
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

        # scale foreground
        if abs(scale - 1.0) > 1e-4:
            new_w = int(w_fg * scale)
            new_h = int(h_fg * scale)
            fg_bgra = cv2.resize(fg_bgra, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            h_fg, w_fg = new_h, new_w

        # centre placement (crop if fg bigger than bg)
        x_off = (w_bg - w_fg) // 2
        y_off = (h_bg - h_fg) // 2

        # compute ROI boundaries (handle fg that overflows bg)
        fg_x1 = max(0, -x_off)
        fg_y1 = max(0, -y_off)
        fg_x2 = min(w_fg, w_bg - x_off)
        fg_y2 = min(h_fg, h_bg - y_off)
        bg_x1 = max(0, x_off)
        bg_y1 = max(0, y_off)
        bg_x2 = bg_x1 + (fg_x2 - fg_x1)
        bg_y2 = bg_y1 + (fg_y2 - fg_y1)

        if bg_x2 <= bg_x1 or bg_y2 <= bg_y1:
            return bg_bgr  # nothing to composite

        fg_patch = fg_bgra[fg_y1:fg_y2, fg_x1:fg_x2]
        alpha = fg_patch[:, :, 3:4].astype(np.float32) / 255.0
        fg_rgb = fg_patch[:, :, :3].astype(np.float32)

        result = bg_bgr.copy()
        bg_patch = result[bg_y1:bg_y2, bg_x1:bg_x2].astype(np.float32)
        blended = fg_rgb * alpha + bg_patch * (1.0 - alpha)
        result[bg_y1:bg_y2, bg_x1:bg_x2] = blended.astype(np.uint8)
        return result

    # ── main transition builder ─────────────────────────────────────────
    def build_transition(
        self,
        frames_a: list[np.ndarray],
        frames_b: list[np.ndarray],
    ) -> list[np.ndarray]:
        """Build the pop-out + motion-blur transition frames.

        *frames_a*: last N frames of Clip A (BGR, uint8)
        *frames_b*: first N frames of Clip B (BGR, uint8)

        Returns a list of *transition_frames* BGR frames that should
        **replace** the tail of Clip A.
        """
        n = min(self.transition_frames, len(frames_a), len(frames_b))
        if n == 0:
            return []

        # Extract foreground from the first frame of Clip B
        fg_bgra = self.extract_foreground(frames_b[0])
        log.info("PopoutTransition: foreground extracted (%dx%d)",
                 fg_bgra.shape[1], fg_bgra.shape[0])

        output: list[np.ndarray] = []
        for i in range(n):
            t = i / max(1, n - 1)  # 0.0 → 1.0

            # --- background: frame from Clip A tail ---
            bg = frames_a[len(frames_a) - n + i].copy()

            # motion blur on background (strong → none)
            blur_strength = int(self.blur_kernel_max * (1.0 - t))
            if blur_strength >= 3:
                bg = self.apply_motion_blur(bg, self.blur_angle, blur_strength)

            # --- optional crossfade: blend in Clip B bg progressively ---
            cf_w = self.crossfade_weight_start + (
                self.crossfade_weight_end - self.crossfade_weight_start
            ) * t
            if cf_w > 0.01:
                b_frame = frames_b[i]
                if b_frame.shape[:2] != bg.shape[:2]:
                    b_frame = cv2.resize(b_frame, (bg.shape[1], bg.shape[0]))
                bg = cv2.addWeighted(bg, 1.0 - cf_w, b_frame, cf_w, 0)

            # --- foreground: scale up from 80 % → 100 % ---
            scale = self.scale_start + (self.scale_end - self.scale_start) * t
            frame = self.composite_fg_on_bg(bg, fg_bgra, scale=scale)

            output.append(frame)

        return output

    # ── convenience: simple crossfade fallback (no rembg) ───────────────
    @staticmethod
    def crossfade_fallback(
        frames_a: list[np.ndarray],
        frames_b: list[np.ndarray],
        n: int = 10,
    ) -> list[np.ndarray]:
        """Simple alpha crossfade when rembg is not available."""
        n = min(n, len(frames_a), len(frames_b))
        if n == 0:
            return []
        out: list[np.ndarray] = []
        for i in range(n):
            t = i / max(1, n - 1)
            a = frames_a[len(frames_a) - n + i]
            b = frames_b[i]
            if a.shape != b.shape:
                b = cv2.resize(b, (a.shape[1], a.shape[0]))
            blended = cv2.addWeighted(a, 1.0 - t, b, t, 0)
            out.append(blended)
        return out


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  2c. Luma Fade Transition (OpenCV)                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class LumaFadeTransition:
    """Transition that reveals Clip B through the dark→light luminance
    regions of Clip A.  The darkest areas of Clip A become transparent
    first, gradually expanding until the full frame is Clip B.
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
            t = i / max(1, n - 1)  # 0.0 → 1.0

            a = frames_a[len(frames_a) - n + i]
            b = frames_b[i]
            if b.shape[:2] != a.shape[:2]:
                b = cv2.resize(b, (a.shape[1], a.shape[0]))

            # Convert Clip A to grayscale → luminance map
            gray = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)

            # Threshold sweeps from 0 → 255 as t goes 0 → 1
            # Pixels darker than threshold → reveal Clip B
            thresh_val = int(t * 255)
            _, mask = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY)
            # mask: 255 = keep A (brighter than threshold), 0 = show B

            # Smooth the mask edges for a soft transition
            blur_k = max(3, int(21 * (1.0 - abs(t - 0.5) * 2)))  # wider at mid
            blur_k = blur_k if blur_k % 2 == 1 else blur_k + 1
            mask_soft = cv2.GaussianBlur(mask, (blur_k, blur_k), 0)

            # Blend using the soft mask
            alpha = mask_soft.astype(np.float32)[:, :, np.newaxis] / 255.0
            blended = (a.astype(np.float32) * alpha +
                       b.astype(np.float32) * (1.0 - alpha))
            output.append(blended.astype(np.uint8))

        return output


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  2d. Whip Pan Transition (OpenCV)                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class WhipPanTransition:
    """High-speed horizontal slide (whip pan) with heavy motion blur.
    The *direction* parameter controls slide direction:
      +1 = slide left  (Clip B enters from the right)
      -1 = slide right (Clip B enters from the left)
    """

    def __init__(
        self,
        transition_frames: int = 6,
        direction: int = 1,
        blur_kernel_max: int = 45,
    ) -> None:
        self.transition_frames = transition_frames
        self.direction = direction  # +1 left, -1 right
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
            t = i / max(1, n - 1)  # 0.0 → 1.0

            a = frames_a[len(frames_a) - n + i]
            b = frames_b[i]
            if b.shape[:2] != a.shape[:2]:
                b = cv2.resize(b, (w, h))

            # Horizontal offset: A slides out, B slides in
            offset = int(t * w) * self.direction

            # Build the composite canvas
            canvas = np.zeros_like(a)

            if self.direction > 0:
                # Clip A slides left, Clip B enters from right
                a_x1_src = min(max(offset, 0), w)
                a_x2_src = w
                a_x1_dst = 0
                a_x2_dst = a_x2_src - a_x1_src

                b_x1_src = 0
                b_x2_src = min(offset, w)
                b_x1_dst = w - offset if offset <= w else 0
                b_x2_dst = w
            else:
                # Clip A slides right, Clip B enters from left
                abs_off = abs(offset)
                a_x1_src = 0
                a_x2_src = max(w - abs_off, 0)
                a_x1_dst = abs_off
                a_x2_dst = w

                b_x1_src = max(w - abs_off, 0)
                b_x2_src = w
                b_x1_dst = 0
                b_x2_dst = min(abs_off, w)

            # Place Clip A (sliding out)
            aw = a_x2_dst - a_x1_dst
            if aw > 0 and (a_x2_src - a_x1_src) > 0:
                src_w = min(a_x2_src - a_x1_src, aw)
                canvas[:, a_x1_dst:a_x1_dst + src_w] = a[:, a_x1_src:a_x1_src + src_w]

            # Place Clip B (sliding in)
            bw = b_x2_dst - b_x1_dst
            if bw > 0 and (b_x2_src - b_x1_src) > 0:
                src_w = min(b_x2_src - b_x1_src, bw)
                canvas[:, b_x1_dst:b_x1_dst + src_w] = b[:, b_x1_src:b_x1_src + src_w]

            # Apply horizontal motion blur (strongest at mid-transition)
            blur_t = 1.0 - abs(t - 0.5) * 2  # peak at t=0.5
            blur_k = int(self.blur_kernel_max * blur_t)
            if blur_k >= 3:
                blur_k = blur_k if blur_k % 2 == 1 else blur_k + 1
                kernel = np.zeros((blur_k, blur_k), dtype=np.float32)
                kernel[blur_k // 2, :] = 1.0 / blur_k
                canvas = cv2.filter2D(canvas, -1, kernel)

            output.append(canvas)

        return output


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  2e. Audio-Reactive Transition Router                                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
class AudioReactiveTransitionRouter:
    """Selects the optimal transition class based on the duration of the
    preceding clip (≈ distance to the next beat drop).

    Routing rules:
      - duration >= 1.5s  (slow beat)    → LumaFadeTransition(12 frames)
      - 0.7s <= dur < 1.5s (beat drop)   → PopoutTransition(10 frames)
      - duration < 0.7s  (fast-paced)    → WhipPanTransition(6 frames),
                                           alternating left ↔ right
    """

    def __init__(self) -> None:
        self._whip_direction: int = 1  # toggles between +1 / -1

    def select(
        self, clip_a_duration: float,
    ) -> LumaFadeTransition | PopoutTransition | WhipPanTransition:
        """Return a transition instance suited to the clip's beat interval."""
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

        # Fast-paced: whip pan, alternate direction
        direction = self._whip_direction
        self._whip_direction *= -1  # toggle for next call
        log.debug("Router: fast beat (%.2fs) → WhipPan dir=%d",
                  clip_a_duration, direction)
        return WhipPanTransition(
            transition_frames=6,
            direction=direction,
            blur_kernel_max=45,
        )


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  3. Text overlay  (MoviePy + Pillow, FFmpeg drawtext fallback)         ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def overlay_text(
    input_video: str | Path,
    output_video: str | Path,
    events: Sequence[dict[str, Any] | Sequence[Any]],
    *,
    font_path: str | Path | None = None,
    font_size_hook: int = 84,
    font_size_feature: int = 64,
    feature_duration: float = 2.8,
    slide_duration: float = 0.65,
    fps: int = 30,
    crf: int = 20,
    preset: str = "veryfast",
    backend: str = "auto",
) -> Path:
    ffmpeg_bin = shutil.which("ffmpeg")
    if backend not in {"auto", "ffmpeg", "moviepy"}:
        raise ValueError("backend must be one of: auto, ffmpeg, moviepy")
    if backend in {"auto", "ffmpeg"} and not ffmpeg_bin:
        raise OverlayError("ffmpeg not found in PATH.")

    src = Path(input_video).expanduser().resolve()
    dst = Path(output_video).expanduser().resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        raise FileNotFoundError(f"Input video not found: {src}")

    font = _resolve_font(font_path)
    parsed = [_parse_event(e) for e in events]
    if not parsed:
        raise ValueError("events must contain at least one item.")

    can_dt = bool(ffmpeg_bin and _ffmpeg_has_drawtext(ffmpeg_bin))

    if backend == "ffmpeg" and not can_dt:
        raise OverlayError("FFmpeg drawtext unavailable. Use backend='moviepy'.")

    if backend == "ffmpeg" or (backend == "auto" and can_dt):
        _overlay_ffmpeg(ffmpeg_bin=ffmpeg_bin, src=src, dst=dst, events=parsed,
                        font_path=font, font_size_hook=font_size_hook,
                        font_size_feature=font_size_feature,
                        feature_duration=feature_duration,
                        slide_duration=slide_duration,
                        fps=fps, crf=crf, preset=preset)
    else:
        _overlay_moviepy(src=src, dst=dst, events=parsed, font_path=font,
                         font_size_hook=font_size_hook,
                         font_size_feature=font_size_feature,
                         feature_duration=feature_duration,
                         slide_duration=slide_duration,
                         fps=fps, crf=crf, preset=preset)
    return dst


# ── MoviePy backend ────────────────────────────────────────────────────────
def _overlay_moviepy(
    *, src: Path, dst: Path, events: Sequence[TextEvent], font_path: Path,
    font_size_hook: int, font_size_feature: int, feature_duration: float,
    slide_duration: float, fps: int, crf: int, preset: str,
) -> None:
    base = VideoFileClip(str(src))
    overlays: list[ImageClip] = []
    tmp_imgs: list[Path] = []

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="overlay_"))
        for ev in events:
            if ev.effect == "hook":
                img = _render_text_img(text=ev.text, font_path=font_path,
                                       font_size=font_size_hook,
                                       max_width=int(base.w * 0.86),
                                       effect="hook")
                p = tmp_dir / f"hook_{len(tmp_imgs):03d}.png"; img.save(p); tmp_imgs.append(p)
                clip = ImageClip(str(p), transparent=True)

                # Slam Down: scale 2.5 → 1.0 over 0.25s, then hold 1.0
                slam_dur = 0.25

                def slam_scale(t, sd=slam_dur):
                    if t < sd:
                        progress = t / sd
                        return 2.5 - 1.5 * progress  # 2.5 → 1.0
                    return 1.0

                center_x = int(base.w / 2 - clip.w / 2)
                center_y = int(base.h / 3 - clip.h / 2)

                clip = (clip
                    .set_start(0.0)
                    .set_duration(max(0.01, min(3.0, base.duration)))
                    .set_position((center_x, center_y))
                    .resize(lambda t: slam_scale(t)))
                overlays.append(clip)
                continue

            start = max(0.0, ev.start)
            if start >= base.duration:
                continue
            img = _render_text_img(text=ev.text, font_path=font_path,
                                   font_size=font_size_feature,
                                   max_width=int(base.w * 0.84),
                                   effect="feature")
            p = tmp_dir / f"feat_{len(tmp_imgs):03d}.png"; img.save(p); tmp_imgs.append(p)
            clip = ImageClip(str(p), transparent=True)

            # Tilt the feature text for dynamic feel
            clip = clip.rotate(-3.5, expand=True)

            dur = min(max(0.2, feature_duration), base.duration - start)
            y_pos = int(base.h * 0.72 - clip.h / 2)
            tx = int(base.w * 0.08)
            entry = max(0.12, slide_duration)

            def motion(t, sx=start, d=entry, tgt=tx, tw=clip.w, yy=y_pos):
                if t < sx:
                    return (-tw - 80.0, float(yy))
                if t < sx + d:
                    p_ = (t - sx) / d
                    # ease-out-back spring overshoot
                    s_val = 1.70158
                    p_rev = p_ - 1.0
                    ease = 1.0 + p_rev * p_rev * ((s_val + 1) * p_rev + s_val)
                    x = (-tw - 80.0) + (tgt + tw + 80.0) * ease
                    return (x, float(yy))
                return (float(tgt), float(yy))

            overlays.append(clip.set_start(start).set_duration(dur).set_position(motion))

        comp = CompositeVideoClip([base, *overlays], size=base.size).set_duration(base.duration)
        comp.write_videofile(
            str(dst), fps=fps, codec="libx264", audio_codec="aac",
            preset=preset, ffmpeg_params=["-crf", str(crf), "-movflags", "+faststart"],
            threads=max(1, (os.cpu_count() or 4) // 2), verbose=False, logger=None,
        )
    except Exception as exc:
        raise OverlayError(f"MoviePy overlay failed: {exc}") from exc
    finally:
        for c in overlays: c.close()
        base.close()
        for ip in tmp_imgs:
            if ip.exists(): ip.unlink()
        if "tmp_dir" in locals() and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ── FFmpeg drawtext backend ────────────────────────────────────────────────
def _overlay_ffmpeg(
    *, ffmpeg_bin: str, src: Path, dst: Path, events: Sequence[TextEvent],
    font_path: Path, font_size_hook: int, font_size_feature: int,
    feature_duration: float, slide_duration: float, fps: int, crf: int, preset: str,
) -> None:
    filters = [_build_drawtext(e, font_path=font_path, font_size_hook=font_size_hook,
                               font_size_feature=font_size_feature,
                               feature_duration=feature_duration,
                               slide_duration=slide_duration) for e in events]
    proc = subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(src), "-vf", ",".join(filters),
         "-r", str(fps), "-c:v", "libx264", "-preset", preset,
         "-crf", str(crf), "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(dst)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise OverlayError(f"FFmpeg drawtext failed:\n{proc.stderr.strip()}")


# ── text rendering helpers ─────────────────────────────────────────────────
def _render_text_img(*, text: str, font_path: Path, font_size: int,
                     max_width: int, effect: str = "feature") -> Image.Image:
    """Render text onto a transparent RGBA image with a rounded-rect background.

    effect="hook":    Yellow Cyberpunk bg + Black text
    effect="feature": Semi-transparent Black bg + White text
    """
    font = ImageFont.truetype(str(font_path), size=font_size)
    m = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(m)
    lines = _wrap(d, text, font, max_width)
    ml = "\n".join(lines)
    bb = d.multiline_textbbox((0, 0), ml, font=font, spacing=10)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    pad = 25
    radius = 15

    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)

    # Style based on effect type
    if effect == "hook":
        bg_color = (255, 215, 0, 255)    # Yellow Cyberpunk
        text_color = (0, 0, 0, 255)      # Black
    else:
        bg_color = (0, 0, 0, 180)        # Semi-transparent Black
        text_color = (255, 255, 255, 255) # White

    # Draw rounded rectangle background
    dr.rounded_rectangle(
        [(0, 0), (w + pad * 2 - 1, h + pad * 2 - 1)],
        radius=radius, fill=bg_color,
    )
    # Draw text (no stroke, no shadow)
    dr.multiline_text((pad, pad), ml, font=font, fill=text_color,
                      spacing=10, align="center")
    return img


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}"
        if draw.textlength(cand, font=font) <= max_w:
            cur = cand
        else:
            lines.append(cur); cur = w
    lines.append(cur)
    return lines


def _resolve_font(font_path: str | Path | None) -> Path:
    if font_path:
        p = Path(font_path).expanduser().resolve()
        if not p.exists():
            raise FileNotFoundError(f"Font not found: {p}")
        return p
    for c in [
        Path("../assets/fonts/BeVietnamPro-Bold.ttf").resolve(),
        Path("../../assets/fonts/BeVietnamPro-Bold.ttf").resolve(),
        Path("assets/fonts/BeVietnamPro-Bold.ttf").resolve(),
        Path("assets/fonts/NotoSans-Regular.ttf").resolve(),
        Path("assets/fonts/NotoSans-Medium.ttf").resolve(),
        Path("assets/fonts/BeVietnamPro-Regular.ttf").resolve(),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/Supplemental/Times New Roman.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]:
        if c.exists():
            return c
    raise FileNotFoundError("No Vietnamese font found. Provide font_path explicitly.")


def _parse_event(item: dict[str, Any] | Sequence[Any]) -> TextEvent:
    if isinstance(item, dict):
        s, t, e = float(item.get("time", 0.0)), str(item.get("text", "")).strip(), str(item.get("effect", "feature")).strip().lower()
    else:
        if len(item) < 3:
            raise ValueError("Event must have [time, text, effect].")
        s, t, e = float(item[0]), str(item[1]).strip(), str(item[2]).strip().lower()
    if not t:
        raise ValueError("Text event content cannot be empty.")
    if e not in {"hook", "feature"}:
        raise ValueError("effect must be: hook or feature")
    return TextEvent(start=s, text=t, effect=e)


def _ffmpeg_has_drawtext(ffmpeg_bin: str) -> bool:
    p = subprocess.run([ffmpeg_bin, "-hide_banner", "-filters"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode == 0 and " drawtext " in p.stdout


def _esc_dt(v: str) -> str:
    for old, new in [("\\", "\\\\"), (":", "\\:"), ("'", "\\'"),
                     ("%", "\\%"), (",", "\\,"), ("[", "\\["), ("]", "\\]")]:
        v = v.replace(old, new)
    return v


def _build_drawtext(ev: TextEvent, *, font_path: Path, font_size_hook: int,
                    font_size_feature: int, feature_duration: float,
                    slide_duration: float) -> str:
    txt, fnt = _esc_dt(ev.text), _esc_dt(str(font_path))
    common = (f"fontfile='{fnt}':text='{txt}':fontcolor=white:line_spacing=12:"
              "box=0:borderw=4:bordercolor=black@0.95:"
              "shadowx=2:shadowy=2:shadowcolor=black@0.85")
    if ev.effect == "hook":
        return (f"drawtext={common}:fontsize={font_size_hook}:"
                "x='(w-text_w)/2':y='(h/3)-(text_h/2)':enable='between(t,0,3)'")
    s = max(0.0, ev.start)
    e = s + max(0.2, feature_duration)
    prog = f"(t-{s:.3f})/{slide_duration:.3f}"
    ease = f"(1-pow(1-{prog},3))"
    x = (f"'if(lt(t,{s:.3f}),-text_w-80,"
         f"if(lt(t,{s + slide_duration:.3f}),"
         f"(-text_w-80)+((w*0.08)+text_w+80)*{ease},w*0.08))'")
    y = "'(h*0.72)-(text_h/2)'"
    return (f"drawtext={common}:fontsize={font_size_feature}:"
            f"x={x}:y={y}:enable='between(t,{s:.3f},{e:.3f})'")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  4. Master pipeline                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════╝
def make_viral(work_dir: str = ".", config: dict = None, preview: bool = False) -> Any:
    # Setup paths from work_dir and config
    work_path = Path(work_dir).resolve()
    input_dir = work_path / "input"
    output_dir = work_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if config and config.get("clips"):
        raw_clips = [Path(c).resolve() for c in config["clips"]]
    else:
        # Fallback to scanning input_dir
        raw_clips = sorted(input_dir.glob("*.mov")) + sorted(input_dir.glob("*.mp4"))
        
    if config and config.get("audio"):
        tiktok_mp3 = Path(config["audio"]).resolve()
    else:
        # Fallback to the first mp3 in input_dir
        mp3s = list(input_dir.glob("*.mp3"))
        tiktok_mp3 = mp3s[0] if mp3s else None
        
    text_events = config.get("text_events", TEXT_EVENTS) if config else TEXT_EVENTS

    t0 = time.time()

    # If preview is requested, we can just return fake metadata similar to build_video
    if preview:
        return {
            "status": "preview_ready",
            "estimated_drops": 10,
            "clips_to_process": len(raw_clips),
            "text_events": text_events
        }


    print("=" * 60)
    print("[1/3] Phân tích beat drops từ nhạc TikTok...")
    print("=" * 60)
    if not tiktok_mp3 or not tiktok_mp3.exists():
        raise FileNotFoundError(f"Audio file not found: {tiktok_mp3}")
        
    drops = detect_beat_drops(tiktok_mp3)
    print(f"  → {len(drops)} beat drops")
    print(f"  → Mẫu: {drops[:12]}")

    print("\n" + "=" * 60)
    print("[2/3] Render video (9:16 crop + beat-sync + nhạc TikTok)...")
    print("=" * 60)
    stage2 = output_dir / "_stage2_tmp.mp4"
    VideoViralEngine(
        input_videos=raw_clips,
        beat_drop_times=drops,
        audio_track=tiktok_mp3,
        seed=42, workers=4, fps=30, crf=20,
        preset="veryfast", working_dir=work_path / ".viral_tmp",
    ).build(stage2)
    print(f"  → Xong stage 2")

    print("\n" + "=" * 60)
    print("[3/3] Đè text động (Hook + Feature slide-in)...")
    print("=" * 60)
    final = output_dir / "viral_final.mp4"
    overlay_text(
        input_video=stage2, output_video=final, events=text_events,
        font_size_hook=78, font_size_feature=58,
        feature_duration=2.6, slide_duration=0.55,
        fps=30, crf=19, preset="veryfast", backend="moviepy",
    )
    stage2.unlink(missing_ok=True)

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print("HOÀN TẤT!")
    print("=" * 60)
    print(f"  → Output : {final}")
    print(f"  → Clips  : {len(raw_clips)} video thô")
    print(f"  → Beats  : {len(drops)} beat drops")
    print(f"  → Text   : {len(text_events)} events")
    print(f"  → Thời gian: {elapsed:.1f}s")
    
    return str(final)

def main() -> None:
    make_viral()


if __name__ == "__main__":
    main()
