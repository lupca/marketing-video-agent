"""
Audio processing module for unbox_engine.
Extracted from make_viral.py and unbox_viral.py.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List

import librosa
import numpy as np

from worker_unbox.unbox_engine.types import BeatInfo, UnboxViralError

log = logging.getLogger(__name__)

def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    lo, hi = float(np.min(v)), float(np.max(v))
    return np.zeros_like(v) if hi - lo < 1e-8 else (v - lo) / (hi - lo)

def detect_beat_drops(
    mp3_path: str | Path,
    *,
    sr: int = 22050,
    hop_length: int = 512,
    min_gap_sec: float = 0.32,
    drop_quantile: float = 0.75,
) -> list[float]:
    """Beat drop detection specifically used by make_viral engine."""
    audio_file = Path(mp3_path).resolve()
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    y, sr_out = librosa.load(str(audio_file), sr=sr, mono=True)
    if y.size == 0:
        return []

    _, y_perc = librosa.effects.hpss(y)
    onset_env = librosa.onset.onset_strength(y=y_perc, sr=sr_out, hop_length=hop_length)

    _, beat_frames = librosa.beat.beat_track(
        y=y_perc, sr=sr_out, hop_length=hop_length, units="frames",
    )
    if beat_frames.size == 0:
        return []

    mel = librosa.feature.melspectrogram(y=y, sr=sr_out, hop_length=hop_length, n_mels=96)
    low_band = np.mean(mel[:10, :], axis=0)
    low_delta = np.maximum(0.0, np.diff(low_band, prepend=low_band[0]))

    onset_n = _normalize(onset_env)
    low_n = _normalize(low_delta)
    score = 0.65 * onset_n + 0.35 * low_n

    threshold = float(np.quantile(score[beat_frames], drop_quantile))
    beat_times = librosa.frames_to_time(beat_frames, sr=sr_out, hop_length=hop_length)

    selected: list[float] = []
    for frame, bt in zip(beat_frames, beat_times):
        if score[frame] < threshold:
            continue
        if selected and bt - selected[-1] < min_gap_sec:
            continue
        selected.append(float(bt))

    return [round(t, 3) for t in selected]


class AudioAnalyzer:
    """Beat detection and audio mixing specifically used by unbox_viral engine."""

    def __init__(self, sr: int = 22050, hop_length: int = 512):
        self.sr = sr
        self.hop_length = hop_length
        self._ffmpeg = shutil.which("ffmpeg")
        if not self._ffmpeg:
            raise UnboxViralError("ffmpeg not found in PATH")

    def detect_beats(
        self,
        audio_path: str | Path,
        *,
        min_gap_sec: float = 0.4,
        drop_quantile: float = 0.72,
    ) -> List[BeatInfo]:
        audio_file = Path(audio_path).resolve()
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        y, sr_out = librosa.load(str(audio_file), sr=self.sr, mono=True)
        if y.size == 0:
            return []

        _, y_perc = librosa.effects.hpss(y)
        onset_env = librosa.onset.onset_strength(
            y=y_perc, sr=sr_out, hop_length=self.hop_length
        )

        _, beat_frames = librosa.beat.beat_track(
            y=y_perc, sr=sr_out, hop_length=self.hop_length, units="frames"
        )
        if beat_frames.size == 0:
            return []

        mel = librosa.feature.melspectrogram(
            y=y, sr=sr_out, hop_length=self.hop_length, n_mels=96
        )
        low_band = np.mean(mel[:10, :], axis=0)
        low_delta = np.maximum(0.0, np.diff(low_band, prepend=low_band[0]))

        onset_n = _normalize(onset_env)
        low_n = _normalize(low_delta)
        score = 0.65 * onset_n + 0.35 * low_n

        threshold = float(np.quantile(score[beat_frames], drop_quantile))
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr_out, hop_length=self.hop_length
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

    def extract_original_audio(
        self, video_path: str | Path, output_path: str | Path
    ) -> Path:
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        self._run_ffmpeg([
            "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "44100", "-ac", "2",
            str(out),
        ])
        return out

    def mix_audio(
        self,
        original_audio: str | Path,
        mp3_audio: str | Path,
        first_beat_time: float,
        total_duration: float,
        output_path: str | Path,
    ) -> Path:
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        bt = max(0.1, first_beat_time)
        filter_complex = (
            f"[0:a]volume='if(lt(t,{bt}),1.0,0.10)':eval=frame[orig];"
            f"[1:a]volume='if(lt(t,{bt}),0.20,1.0)':eval=frame[bgm];"
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

    def speed_ramp_audio(
        self,
        audio_path: str | Path,
        speed: float,
        output_path: str | Path,
    ) -> Path:
        out = Path(output_path).resolve()
        new_rate = int(44100 * speed)
        self._run_ffmpeg([
            "-i", str(audio_path),
            "-af", f"asetrate={new_rate},aresample=44100",
            str(out),
        ])
        return out

    def trim_audio_intro(
        self,
        audio_path: str | Path,
        trim_sec: float,
        output_path: str | Path,
    ) -> Path:
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        log.info(
            f"  Trimming {trim_sec:.2f}s intro from audio → "
            f"beat drop shifts to TikTok-safe range"
        )
        self._run_ffmpeg([
            "-i", str(audio_path),
            "-ss", f"{trim_sec:.3f}",
            "-c", "copy",
            str(out),
        ])
        return out

    def _run_ffmpeg(self, args: List[str]) -> subprocess.CompletedProcess:
        cmd = [self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise UnboxViralError(
                f"FFmpeg failed: {' '.join(cmd)}\n{proc.stderr.strip()}"
            )
        return proc
