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
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared_core.audio_utils import enforce_early_beat_drop
from worker_unbox.unbox_engine.types import TextEventUnbox, UnboxViralError
from worker_unbox.unbox_engine.audio import AudioAnalyzer
from worker_unbox.unbox_engine.video_unbox import VideoProcessor, Renderer, probe_fps

logger = logging.getLogger(__name__)


def _parse_text_events(
    events: List[Dict[str, Any]],
    beat_times: List[float],
) -> List[TextEventUnbox]:
    """
    Parse text events from config. Auto-assign beat times for events
    with time=None, ensuring a minimum gap to prevent overlaps.
    """
    parsed: List[TextEventUnbox] = []
    beat_idx = 0
    last_event_time = 0.0

    for ev in events:
        text = str(ev.get("text", "")).strip()
        event_type = str(ev.get("type", ev.get("effect", "feature"))).lower()
        raw_time = ev.get("time")

        if not text:
            continue

        if event_type == "hook":
            parsed.append(TextEventUnbox(start=0.0, text=text, event_type="hook"))
            # Hook stays slightly longer, texts should not start before 2.0s
            last_event_time = 2.0
            continue

        if raw_time is None:
            # Snap to a beat that is at least 2.0 seconds after the last event
            target_min_time = last_event_time + 2.0
            assigned_bt = None

            while beat_idx < len(beat_times):
                bt = beat_times[beat_idx]
                beat_idx += 1
                if bt >= target_min_time:
                    assigned_bt = bt
                    break

            if assigned_bt is None:
                # Out of beats, just space it manually
                assigned_bt = target_min_time

            parsed.append(TextEventUnbox(start=assigned_bt, text=text, event_type="feature"))
            last_event_time = assigned_bt
        else:
            t = float(raw_time)
            parsed.append(TextEventUnbox(start=t, text=text, event_type=event_type))
            last_event_time = max(last_event_time, t)

    return parsed


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

    # ── Pacing Constraint: Trim long intro if beat drop arrives too late ──
    audio_path, beat_times, was_trimmed = enforce_early_beat_drop(
        audio_path=audio_path,
        beat_times=beat_times,
        temp_dir=tmp_dir,
        ffmpeg_bin=audio_analyzer._ffmpeg,
        detect_beat_func=lambda p: [b.time for b in audio_analyzer.detect_beats(p)],
    )
    
    if was_trimmed:
        first_beat = beat_times[0] if beat_times else 3.75
        logger.info(f"  → After trim: first beat now at {first_beat:.2f}s")
        logger.info(f"  → Re-detected {len(beat_times)} beats: {beat_times[:10]}")

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
    src_fps = probe_fps(primary_video)
    segment_files: List[Path] = []

    final_video_beat_times = []
    actual_beat_time_in_video = 0.0
    accumulated_video_duration = 0.0
    beat_found = False

    for i, seg in enumerate(processed_segments):
        actual_duration = (seg.end - seg.start) / seg.speed_factor
        if seg.is_beat_cut:
            final_video_beat_times.append(accumulated_video_duration)
            if not beat_found:
                actual_beat_time_in_video = accumulated_video_duration
                beat_found = True
        accumulated_video_duration += actual_duration

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

    # Parse text events (auto-assign to musical beats)
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

    # Extract synced audio from the concatenated video
    synced_audio = tmp_dir / "synced_audio.wav"
    audio_analyzer.extract_original_audio(concat_out, synced_audio)

    video_duration = renderer._probe_duration(video_for_mux)
    mixed_audio = tmp_dir / "mixed_audio.wav"
    
    mix_beat_time = actual_beat_time_in_video if beat_found else first_beat
    audio_analyzer.mix_audio(
        synced_audio, audio_path, mix_beat_time,
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    make_unbox_viral()
