"""
make_viral specific video processing core.
"""
from __future__ import annotations

import concurrent.futures
import logging
import os
import random
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

try:
    from shared_core.gpu_utils import detect_ffmpeg_hw_encoder, get_ffmpeg_encoder_args
except ImportError:
    def detect_ffmpeg_hw_encoder() -> str:
        return "libx264"
    def get_ffmpeg_encoder_args(crf: int = 20, preset: str = "veryfast") -> list[str]:
        return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]

import cv2
import numpy as np

from worker_unbox.unbox_engine.types import SceneSpec, VideoTrimInfo, VideoProcessingError, FFmpegNotFoundError
from worker_unbox.unbox_engine.transitions import AudioReactiveTransitionRouter, PopoutTransition

log = logging.getLogger(__name__)

class VideoViralEngine:
    _SILENCE_START_RE = re.compile(r"silence_start:\s*(\d+(?:\.\d+)?)")
    _SILENCE_END_RE = re.compile(r"silence_end:\s*(\d+(?:\.\d+)?)")

    def __init__(
        self,
        input_videos: Sequence[Union[str, Path]],
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
        workers: Optional[int] = None,
        seed: Optional[int] = None,
        working_dir: Union[str, Path] = ".viral_engine_tmp",
        keep_temp: bool = False,
        beat_drop_times: Optional[Sequence[float]] = None,
        audio_track: Union[str, Path, None] = None,
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

    def build(self, output_path: Union[str, Path]) -> Path:
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
        active: Optional[float] = None
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
    def _nearest_beat(beats: List[float], target: float) -> Optional[float]:
        if not beats: return None
        a = np.asarray(beats)
        return float(a[int(np.argmin(np.abs(a - target)))])

    def _render_scene(self, scene: SceneSpec, out: Path) -> None:
        vf = (
            f"scale={self.target_width}:{self.target_height}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={self.target_width}:{self.target_height},"
            f"zoompan=z='min(zoom+0.0015,1.15)'"
            f":x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2'"
            f":d=1:s={self.target_width}x{self.target_height}"
            f":fps={self.fps}"
        )
        enc_args = get_ffmpeg_encoder_args(crf=self.crf, preset=self.preset)
        self._run([
            self.ffmpeg_bin, "-y",
            "-ss", f"{scene.start:.3f}", "-t", f"{scene.duration:.3f}",
            "-i", str(scene.source),
            "-map", "0:v:0",
            "-vf", vf,
            *enc_args,
            "-pix_fmt", "yuv420p",
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

        try:
            self._concat_with_smart_transitions(files, output)
            return
        except Exception as exc:
            log.warning("Smart transitions failed, falling back to xfade: %s", exc)

        self._concat_with_xfade(files, output)

    def _concat_with_smart_transitions(
        self, files: Sequence[Path], output: Path,
    ) -> None:
        router = AudioReactiveTransitionRouter()
        durations = [self._probe_duration(f) for f in files]
        all_scene_frames: list[list[np.ndarray]] = []
        for f in files:
            frames = self._decode_video(f)
            if not frames:
                raise VideoProcessingError(f"Could not decode frames from {f}")
            all_scene_frames.append(frames)

        final_frames: list[np.ndarray] = []
        for idx, scene_frames in enumerate(all_scene_frames):
            if idx == 0:
                final_frames.extend(scene_frames)
                continue

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
                    log.warning("Transition failed on scene %d (%s), using crossfade fallback: %s",
                                idx, type(transition).__name__, exc)
                    trans_out = PopoutTransition.crossfade_fallback(tail_a, head_b, usable_n)
                if trans_out:
                    final_frames[-usable_n:] = trans_out
                final_frames.extend(cur_frames[usable_n:])
            else:
                final_frames.extend(cur_frames)
        self._encode_frames(final_frames, output)

    def _decode_video(self, path: Path) -> list[np.ndarray]:
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
        enc_args = get_ffmpeg_encoder_args(crf=self.crf, preset=self.preset)
        self._run([
            self.ffmpeg_bin, "-y",
            "-i", str(tmp_raw),
            *enc_args,
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            "-movflags", "+faststart",
            "-an",
            str(output),
        ])
        tmp_raw.unlink(missing_ok=True)

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
        enc_args = get_ffmpeg_encoder_args(crf=self.crf, preset=self.preset)
        self._run([
            self.ffmpeg_bin, "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            *enc_args,
            "-pix_fmt", "yuv420p",
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
            "-ar", "44100", "-ac", "2", "-b:a", "192k",
            "-t", f"{dur:.3f}", "-movflags", "+faststart", str(output),
        ])
