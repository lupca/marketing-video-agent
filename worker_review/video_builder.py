#!/usr/bin/env python3
"""
Video Builder — TikTok / Reels Automation (9:16, 1080×1920)
===========================================================
Thin orchestrator that reads ``input.json`` and delegates to
focused modules in ``video_pipeline/``.

Usage:
    python video_builder.py                   # defaults to ./input.json
    python video_builder.py path/to/cfg.json
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from shared_core.gpu_utils import detect_ffmpeg_hw_encoder
except ImportError:
    def detect_ffmpeg_hw_encoder() -> str:
        return "libx264"

from subtitle_burner import SubtitleBurner
from video_pipeline import make_logo_overlay
from caption_maker import CaptionMaker
from video_pipeline.clip_assembler import build_segment_clips
from video_pipeline.effects import apply_effects
from video_pipeline.transitions import (
    TRANSITION_DUR,
    TRANSITION_STYLES,
    apply_transition,
    make_flash_clip,
)
from video_pipeline.audio_mixer import mix_audio

from PIL import Image

# ─── Compat: Pillow ≥ 10 removed ANTIALIAS; moviepy 1.x still references it ─
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from moviepy.editor import CompositeVideoClip

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VideoBuilder")


# ════════════════════════════════════════════════════════════════════════════
# VideoBuilder
# ════════════════════════════════════════════════════════════════════════════
class VideoBuilder:
    """Orchestrates the full video-production pipeline from a JSON config."""

    def __init__(self, config_path: str = None, config_data: dict = None, preview: bool = False) -> None:
        self.preview = preview
        if config_data:
            self.config = config_data
            self.base_dir = Path(".").resolve() if not config_path else Path(config_path).parent.resolve()
        else:
            self.config_path = Path(config_path).resolve()
            self.base_dir = self.config_path.parent
            self.config = self._load_config()

        rs = self.config.get("render_settings", {})
        self.width: int = rs.get("resolution", [1080, 1920])[0]
        self.height: int = rs.get("resolution", [1080, 1920])[1]
        self.auto_subtitle: bool = rs.get("auto_subtitle", False)
        self.default_pacing: Dict[str, float] = rs.get("pacing", {})

        self.assets: Dict = self.config.get("assets", {})
        self.video_folders: Dict[str, str] = self.assets.get("video_folders", {})
        self.timeline: List[Dict] = self.config.get("timeline_script", [])

        self._open_clips: List = []

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ────────── Main Build Pipeline ───────────────────────────────────────

    def build(self) -> str:
        """Execute the full pipeline and return the output file path."""
        project_id = self.config["metadata"]["project_id"]
        out_path = self.base_dir / f"output/{project_id}.mp4"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("=" * 56)
        logger.info(f"Project  : {project_id}")
        logger.info(f"Output   : {self.width}×{self.height}  |  {len(self.timeline)} segments")
        logger.info("=" * 56)

        video_layers: List = []
        subtitle_entries: List[Dict] = []
        sfx_data: List[Tuple] = []
        cursor_t = 0.0
        trans_dur = TRANSITION_DUR

        for idx, seg in enumerate(self.timeline):
            name = seg["segment"]
            s_cfg, e_cfg = seg["time_range"]
            dur_cfg = e_cfg - s_cfg
            logger.info(f"\n▸ {name}  [cfg {s_cfg}s → {e_cfg}s]  (requested {dur_cfg}s)")

            # 1) Assemble video for this segment
            clip = build_segment_clips(
                seg, self.video_folders, self.base_dir,
                self.width, self.height, self._open_clips,
                self.default_pacing,
            )
            actual_dur = clip.duration

            # 2) Inter-segment transition
            if idx > 0:
                style = TRANSITION_STYLES[(idx - 1) % len(TRANSITION_STYLES)]
                if style == "flash":
                    flash = make_flash_clip(trans_dur * 0.6, self.width, self.height)
                    flash = flash.set_start(cursor_t)
                    video_layers.append(flash)
                    cursor_t += trans_dur * 0.6
                    logger.info(f"  ⚡ Transition: flash ({trans_dur * 0.6:.2f}s)")
                else:
                    cursor_t -= trans_dur
                    clip = apply_transition(clip, style, trans_dur)
                    logger.info(f"  🔀 Transition: {style} ({trans_dur}s overlap)")

            seg_start = cursor_t

            # 3) Capture original audio BEFORE muting (for SFX boost)
            mix_cfg = seg.get("audio_mix", {})
            boost = mix_cfg.get("boost_original_sfx", 0)
            if boost > 0 and clip.audio is not None:
                sfx_data.append((clip.audio, seg_start, boost))
                logger.info(f"  SFX boost ×{boost} preserved")
            else:
                sfx_data.append((None, seg_start, 0))

            # 4) Mute original audio on the video track
            clip = clip.without_audio()

            # 5) Apply non-speed visual effects
            clip = apply_effects(clip, seg, seg_start, self.width, self.height, logger)

            # 6) Place on the actual timeline
            clip = clip.set_start(seg_start)
            video_layers.append(clip)

            # 7) Queue text for SubtitleBurner
            txt = seg.get("text_overlay")
            if txt:
                subtitle_entries.append({
                    "start":           seg_start,
                    "end":             seg_start + actual_dur,
                    "text":            txt,
                    "highlight_words": seg.get("highlight_words", []),
                })
                logger.info(f'  Subtitle queued: "{txt[:50]}"')

            cursor_t = seg_start + actual_dur
            logger.info(f"  → placed at {seg_start:.2f}s – {cursor_t:.2f}s")

        # ── Composite ────────────────────────────────────────────────────
        total_dur = cursor_t
        logger.info(f"\nTotal duration: {total_dur:.2f}s")

        logo_clip = make_logo_overlay(
            base_dir=self.base_dir,
            assets=self.assets,
            frame_w=self.width,
            frame_h=self.height,
            total_dur=total_dur,
            logger=logger,
        )
        composite_layers = video_layers + ([logo_clip] if logo_clip else [])

        final = CompositeVideoClip(
            composite_layers,
            size=(self.width, self.height),
        ).set_duration(total_dur)

        # ── Audio mix ────────────────────────────────────────────────────
        logger.info("Mixing audio …")
        final = final.set_audio(
            mix_audio(self.base_dir, self.assets, total_dur, sfx_data, self._open_clips)
        )


        # ── Render ───────────────────────────────────────────────────────
        raw_path = out_path.parent / f"{project_id}_raw.mp4"
        logger.info(f"\nRendering → {raw_path}")
        hw_codec = detect_ffmpeg_hw_encoder()
        write_kwargs = {
            "fps": 30,
            "codec": hw_codec,
            "audio_codec": "aac",
            "threads": 4,
            "logger": "bar",
        }
        if hw_codec == "h264_nvenc":
            write_kwargs["ffmpeg_params"] = ["-preset", "p4", "-rc", "vbr", "-cq", "23"]
        else:
            write_kwargs["preset"] = "ultrafast"
            
        final.write_videofile(str(raw_path), **write_kwargs)

        self._cleanup()

        # ── Subtitle burn (ASS hard-burn via FFmpeg) ──────────────────────
        if subtitle_entries:
            ass_path = str(out_path.parent / f"{project_id}.ass")
            try:
                logger.info("\nBurning ASS subtitles …")
                SubtitleBurner(self.config).process(
                    subtitle_entries,
                    str(raw_path),
                    str(out_path),
                    ass_path,
                )
                raw_path.unlink()
            except Exception as exc:
                logger.warning(f"Subtitle burn failed: {exc}")
                logger.warning("Using raw video (no burned subtitles) as fallback.")
                raw_path.rename(out_path)
        else:
            raw_path.rename(out_path)

        # ── Auto-caption: WhisperX forced alignment (Hormozi style) ─────────
        if self.auto_subtitle:
            audio_cfg  = self.assets.get("audio", {})
            vo_path    = audio_cfg.get("voiceover_path")
            script_rel = audio_cfg.get("voiceover_script")
            if vo_path and script_rel:
                vo_abs     = str(self.base_dir / vo_path)
                script_abs = str(self.base_dir / script_rel)
                cap_ass    = str(out_path.parent / f"{project_id}_captions.ass")
                cap_tmp    = out_path.parent / f"{project_id}_captioned.mp4"
                try:
                    logger.info("\nGenerating Hormozi captions (WhisperX alignment) …")
                    maker = CaptionMaker(
                        language=audio_cfg.get("voiceover_lang", "vi"),
                        device=audio_cfg.get("whisper_device", "auto"),
                    )
                    maker.generate_ass(vo_abs, script_abs, cap_ass)
                    logger.info("Burning captions onto final video …")
                    maker.burn(str(out_path), cap_ass, str(cap_tmp))
                    out_path.unlink()
                    cap_tmp.rename(out_path)
                    logger.info(f"  ✓ Captions burned → {out_path}")
                except Exception as exc:
                    logger.warning(f"Caption burn skipped: {exc}")
            else:
                logger.warning(
                    "auto_subtitle=true but 'voiceover_script' not set in "
                    "assets.audio — skipping WhisperX caption step."
                )

        logger.info(f"\n✓ Done → {out_path}")
        return str(out_path)

    # ────────── Cleanup ───────────────────────────────────────────────────

    def _cleanup(self) -> None:
        """Close all opened clips to free memory / file handles."""
        for c in self._open_clips:
            try:
                c.close()
            except Exception:
                pass
        self._open_clips.clear()


# ─── Entry Point ────────────────────────────────────────────────────────────
def build_video(config: Any = "input.json", preview: bool = False) -> Any:
    """API-friendly function: build one complete video and return output path, or return metadata if preview=True."""
    if isinstance(config, dict):
        builder = VideoBuilder(config_data=config, preview=preview)
    else:
        builder = VideoBuilder(config_path=config, preview=preview)

    if preview:
        # Just return rough segments logic without rendering an entire video
        preview_data = {
            "project_id": builder.config.get("metadata", {}).get("project_id", "preview"),
            "resolution": [builder.width, builder.height],
            "estimated_segments": len(builder.timeline),
            "timeline": builder.timeline
        }
        return preview_data
    
    return builder.build()


def main() -> None:
    cfg = sys.argv[1] if len(sys.argv) > 1 else "input.json"
    if not os.path.exists(cfg):
        logger.error(f"Config file not found: {cfg}")
        sys.exit(1)
    build_video(cfg)


if __name__ == "__main__":
    main()
