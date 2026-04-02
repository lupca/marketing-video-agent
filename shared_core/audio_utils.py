import logging
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple

logger = logging.getLogger(__name__)

def enforce_early_beat_drop(
    audio_path: Path,
    beat_times: List[float],
    temp_dir: Path,
    ffmpeg_bin: str,
    detect_beat_func: Callable[[Path], List[float]]
) -> Tuple[Path, List[float], bool]:
    """
    Trim audio if the first beat drop is too late (> 5.0s).
    Forces the first drop to be around 3.75s.
    """
    if not beat_times:
        return audio_path, beat_times, False

    first_beat = beat_times[0]
    if first_beat <= 5.0:
        return audio_path, beat_times, False

    trim_amount = first_beat - 3.75
    logger.warning(
        f"  ⚠ First beat drop at {first_beat:.2f}s is too late "
        f"(deadline: 5.0s). Trimming {trim_amount:.2f}s from MP3 intro."
    )

    temp_dir.mkdir(parents=True, exist_ok=True)
    trimmed_audio = temp_dir / f"trimmed_{audio_path.name}"
    
    cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(audio_path),
        "-ss", f"{trim_amount:.3f}",
        "-c", "copy",
        str(trimmed_audio),
    ]
    
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"FFmpeg failed to trim audio: {proc.stderr}")
        return audio_path, beat_times, False
        
    new_beats = detect_beat_func(trimmed_audio)
    return trimmed_audio, new_beats, True
