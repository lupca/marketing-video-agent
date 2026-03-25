"""
make_viral.py – One-command viral video generator
===================================================
Refactored pipeline using `unbox_engine`.
  1. Beat-drop detection (librosa)
  2. Trim silence + beat-synced scene cutting + 9:16 center-crop
  3. TikTok audio muxing
  4. Dynamic text overlay (Hook + Feature slide-in)

Usage:
    python3 make_viral.py
"""
from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import Any

from shared_core.audio_utils import enforce_early_beat_drop
from worker_unbox.unbox_engine.audio import detect_beat_drops
from worker_unbox.unbox_engine.text_overlay import overlay_text_make_viral
from worker_unbox.unbox_engine.video_viral import VideoViralEngine

log = logging.getLogger(__name__)

# Global static events fallback
TEXT_EVENTS: list[dict[str, Any]] = [
    {"time": 0.0, "text": "VỢT CẦU LÔNG SIÊU ĐỈNH 🔥", "effect": "hook"},
    {"time": 3.2, "text": "Cuốn cán chính hãng", "effect": "feature"},
    {"time": 5.8, "text": "Khung carbon siêu nhẹ", "effect": "feature"},
    {"time": 8.4, "text": "Cân bằng hoàn hảo", "effect": "feature"},
]

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

    # If preview is requested, return fake metadata
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

    tiktok_mp3_path, drops, was_trimmed = enforce_early_beat_drop(
        audio_path=Path(tiktok_mp3),
        beat_times=drops,
        temp_dir=work_path / ".viral_tmp",
        ffmpeg_bin=shutil.which("ffmpeg"),
        detect_beat_func=detect_beat_drops,
    )
    tiktok_mp3 = str(tiktok_mp3_path)
    if was_trimmed:
        print(f"  → Đã cắt intro audio, beat đầu tiên rơi vào {drops[0]:.2f}s")

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
    overlay_text_make_viral(
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
