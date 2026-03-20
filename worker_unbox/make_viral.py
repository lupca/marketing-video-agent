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

import librosa
import numpy as np
from moviepy.editor import CompositeVideoClip, ImageClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFont

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

        xfade_duration = 0.5
        effects = ["fade", "slideleft"]

        # Probe actual durations of rendered scene files
        durations = [self._probe_duration(f) for f in files]

        n = len(files)
        inputs: list[str] = []
        for f in files:
            inputs.extend(["-i", str(f)])

        # Build xfade filter chain:
        # [0][1]xfade=transition=fade:duration=0.3:offset=O0[v01];
        # [v01][2]xfade=transition=slideleft:duration=0.3:offset=O1[v02]; ...
        filter_parts: list[str] = []
        # Running offset: each successive xfade reduces total by xfade_duration
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
                                       max_width=int(base.w * 0.86))
                p = tmp_dir / f"hook_{len(tmp_imgs):03d}.png"; img.save(p); tmp_imgs.append(p)
                clip = ImageClip(str(p), transparent=True)
                overlays.append(
                    clip.set_start(0.0)
                        .set_duration(max(0.01, min(3.0, base.duration)))
                        .set_position((int(base.w / 2 - clip.w / 2),
                                       int(base.h / 3 - clip.h / 2)))
                )
                continue

            start = max(0.0, ev.start)
            if start >= base.duration:
                continue
            img = _render_text_img(text=ev.text, font_path=font_path,
                                   font_size=font_size_feature,
                                   max_width=int(base.w * 0.84))
            p = tmp_dir / f"feat_{len(tmp_imgs):03d}.png"; img.save(p); tmp_imgs.append(p)
            clip = ImageClip(str(p), transparent=True)
            dur = min(max(0.2, feature_duration), base.duration - start)
            y_pos = int(base.h * 0.72 - clip.h / 2)
            tx = int(base.w * 0.08)
            entry = max(0.12, slide_duration)

            def motion(t, sx=start, d=entry, tgt=tx, tw=clip.w, yy=y_pos):
                if t < sx:
                    return (-tw - 80.0, float(yy))
                if t < sx + d:
                    p_ = (t - sx) / d
                    x = (-tw - 80.0) + (tgt + tw + 80.0) * (1.0 - pow(1.0 - p_, 3))
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
                     max_width: int, stroke_width: int = 4) -> Image.Image:
    font = ImageFont.truetype(str(font_path), size=font_size)
    m = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(m)
    lines = _wrap(d, text, font, max_width)
    ml = "\n".join(lines)
    bb = d.multiline_textbbox((0, 0), ml, font=font, spacing=10, stroke_width=stroke_width)
    w, h, pad = bb[2] - bb[0], bb[3] - bb[1], 18
    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    # shadow layer
    dr.multiline_text((pad + 3, pad + 3), ml, font=font, fill=(0, 0, 0, 220),
                      spacing=10, stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255), align="center")
    # main layer
    dr.multiline_text((pad, pad), ml, font=font, fill=(255, 255, 255, 255),
                      spacing=10, stroke_width=stroke_width, stroke_fill=(0, 0, 0, 255), align="center")
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
                "x=(w-text_w)/2:y=(h/3)-(text_h/2):enable='between(t,0,3)'")
    s = max(0.0, ev.start)
    e = s + max(0.2, feature_duration)
    prog = f"(t-{s:.3f})/{slide_duration:.3f}"
    ease = f"(1-pow(1-{prog},3))"
    x = (f"if(lt(t,{s:.3f})\\,-text_w-80\\,"
         f"if(lt(t,{s + slide_duration:.3f})\\,"
         f"(-text_w-80)+((w*0.08)+text_w+80)*{ease}\\,w*0.08))")
    return (f"drawtext={common}:fontsize={font_size_feature}:"
            f"x={x}:y=(h*0.72)-(text_h/2):enable='between(t,{s:.3f},{e:.3f})'")


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
        fps=30, crf=19, preset="veryfast", backend="auto",
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
