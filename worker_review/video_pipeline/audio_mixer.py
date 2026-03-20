"""
video_pipeline/audio_mixer.py — 3-track audio mixing (VO + BGM + SFX).
"""

from pathlib import Path
from typing import Dict, List, Tuple

from moviepy.editor import AudioFileClip, CompositeAudioClip, concatenate_audioclips


def mix_audio(
    base_dir: Path,
    assets: Dict,
    total_dur: float,
    sfx_tracks: List[Tuple],
    open_clips: List,
) -> CompositeAudioClip:
    """
    Build the final 3-track audio mix:
        Track 1 — Voiceover            (boosted ×1.5 for clarity)
        Track 2 — BGM, looped & ducked  (volume × 0.08)
        Track 3 — Original clip SFX     (muted everywhere EXCEPT
                   segments flagged with ``boost_original_sfx``)
    """
    audio_cfg = assets.get("audio", {})
    vo_path = audio_cfg.get("voiceover_path")
    bgm_path = audio_cfg.get("bgm_path")

    tracks = []

    # Track 1: Voiceover (boosted for clarity over BGM)
    if vo_path:
        vo = AudioFileClip(str(base_dir / vo_path)).volumex(1.5)
        open_clips.append(vo)
        if vo.duration > total_dur:
            vo = vo.subclip(0, total_dur)
        tracks.append(vo)

    # Track 2: BGM — loop if shorter than total, duck to 0.08
    if bgm_path:
        bgm = AudioFileClip(str(base_dir / bgm_path))
        open_clips.append(bgm)
        if bgm.duration < total_dur:
            reps = int(total_dur / bgm.duration) + 1
            bgm = concatenate_audioclips([bgm] * reps)
        bgm = bgm.subclip(0, total_dur).volumex(0.2)
        tracks.append(bgm)

    # Track 3: Original SFX (only where boost > 0)
    for audio_clip, start_time, volume in sfx_tracks:
        if audio_clip is not None and volume > 0:
            tracks.append(audio_clip.volumex(volume).set_start(start_time))

    return CompositeAudioClip(tracks)
