"""
Text overlay module. Supports both make_viral and unbox_viral patterns.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Sequence, Union

try:
    from shared_core.gpu_utils import detect_ffmpeg_hw_encoder, get_ffmpeg_encoder_args
except ImportError:
    def detect_ffmpeg_hw_encoder() -> str:
        return "libx264"
    def get_ffmpeg_encoder_args(crf: int = 20, preset: str = "veryfast") -> list[str]:
        return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf)]

from moviepy.editor import CompositeVideoClip, ImageClip, VideoFileClip
from PIL import Image, ImageDraw, ImageFont

from worker_unbox.unbox_engine.types import OverlayError, TextEventMakeViral

log = logging.getLogger(__name__)

# ── Shared Text Rendering Helpers ──────────────────────────────────────────

def resolve_font(font_path: Union[str, Path, None] = None) -> Path:
    if font_path:
        p = Path(font_path).resolve()
        if p.exists():
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
        Path("/System/Library/Fonts/Helvetica.ttc"),
    ]:
        if c.exists():
            return c
    raise FileNotFoundError("No Vietnamese font found. Provide font_path explicitly.")

def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
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
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines

def render_text_img(text: str, font_path: Path, font_size: int,
                    max_width: int, effect: str = "feature") -> Image.Image:
    """Render text onto a transparent RGBA image with a rounded-rect background."""
    font = ImageFont.truetype(str(font_path), size=font_size)
    m = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(m)
    lines = wrap_text(d, text, font, max_width)
    ml = "\n".join(lines)
    bb = d.multiline_textbbox((0, 0), ml, font=font, spacing=10)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    pad = 25
    radius = 15

    img = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)

    if effect == "hook":
        bg_color = (255, 215, 0, 255)    # Yellow Cyberpunk
        text_color = (0, 0, 0, 255)      # Black
    else:
        bg_color = (0, 0, 0, 180)        # Semi-transparent Black
        text_color = (255, 255, 255, 255) # White

    # Background box
    dr.rounded_rectangle(
        [(0, 0), (w + pad * 2 - 1, h + pad * 2 - 1)],
        radius=radius, fill=bg_color,
    )
    # Shadow text
    shadow_off = 3
    dr.multiline_text((pad + shadow_off, pad + shadow_off), ml, font=font, fill=(0, 0, 0, 180),
                      spacing=10, align="center")
    # Main text with stroke
    dr.multiline_text((pad, pad), ml, font=font, fill=text_color,
                      stroke_width=2, stroke_fill=(0, 0, 0, 255),
                      spacing=10, align="center")
    return img


# ── make_viral specific text overlay ──────────────────────────────────────

def parse_make_viral_event(item: Union[dict[str, Any], Sequence[Any]]) -> TextEventMakeViral:
    if isinstance(item, dict):
        s = float(item.get("time", item.get("start", 0.0)))
        t = str(item.get("text", "")).strip()
        e = str(item.get("effect", item.get("type", "feature"))).strip().lower()
    else:
        if len(item) < 3:
            raise ValueError("Event must have [time, text, effect].")
        s = float(item[0])
        t = str(item[1]).strip()
        e = str(item[2]).strip().lower()
        
    if not t:
        raise ValueError("Text event content cannot be empty.")
    if e not in {"hook", "feature"}:
        raise ValueError("effect must be: hook or feature")
    return TextEventMakeViral(start=s, text=t, effect=e)


def _ffmpeg_has_drawtext(ffmpeg_bin: str) -> bool:
    p = subprocess.run([ffmpeg_bin, "-hide_banner", "-filters"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode == 0 and " drawtext " in p.stdout


def _esc_dt(v: str) -> str:
    for old, new in [("\\", "\\\\"), (":", "\\:"), ("'", "\\'"),
                     ("%", "\\%"), (",", "\\,"), ("[", "\\["), ("]", "\\]")]:
        v = v.replace(old, new)
    return v


def _build_drawtext(ev: TextEventMakeViral, *, font_path: Path, font_size_hook: int,
                    font_size_feature: int, feature_duration: float,
                    slide_duration: float, y_offset: int = 0) -> str:
    txt, fnt = _esc_dt(ev.text), _esc_dt(str(font_path))
    
    if ev.effect == "hook":
        # Yellow background, black text
        color = "black"
        box_color = "0xFFD700@1.0"
        fs = font_size_hook
        y = "'(h/3)-(text_h/2)'"
        enable = "enable='between(t,0,3)'"
    else:
        # Semi-transparent black background, white text
        color = "white"
        box_color = "black@0.70"
        fs = font_size_feature
        y = f"'(h*0.72)-(text_h/2)+{y_offset}'"
        enable = f"enable='between(t,{ev.start:.3f},{ev.start + feature_duration:.3f})'"

    common = (f"fontfile='{fnt}':text='{txt}':fontcolor={color}:fontsize={fs}:line_spacing=12:"
              f"box=1:boxcolor={box_color}:boxborderw=20:"
              f"borderw=2:bordercolor=black:"
              "shadowx=3:shadowy=3:shadowcolor=black@0.50")

    if ev.effect == "hook":
        return f"drawtext={common}:x='(w-text_w)/2':y={y}:{enable}"
    
    s = max(0.0, ev.start)
    prog = f"(t-{s:.3f})/{slide_duration:.3f}"
    ease = f"(1-pow(1-{prog},3))"
    x = (f"'if(lt(t,{s:.3f}),-text_w-80,"
         f"if(lt(t,{s + slide_duration:.3f}),"
         f"(-text_w-80)+((w*0.08)+text_w+80)*{ease},w*0.08))'")
    
    return f"drawtext={common}:x={x}:y={y}:{enable}"


def _overlay_ffmpeg(
    *, ffmpeg_bin: str, src: Path, dst: Path, events: Sequence[TextEventMakeViral],
    font_path: Path, font_size_hook: int, font_size_feature: int,
    feature_duration: float, slide_duration: float, fps: int, crf: int, preset: str,
) -> None:
    sorted_events = sorted(events, key=lambda e: e.start if e.effect == "feature" else 0.0)
    filters = []
    processed_features: list[tuple[float, float, int]] = [] # (start, end, y_offset)

    for ev in sorted_events:
        y_off = 0
        if ev.effect == "feature":
            start = max(0.0, ev.start)
            end = start + max(0.2, feature_duration)
            concurrent = 0
            for s_old, e_old, _ in processed_features:
                if not (start >= e_old or end <= s_old):
                    concurrent += 1
            y_off = concurrent * 85
            processed_features.append((start, end, y_off))
            
        f = _build_drawtext(ev, font_path=font_path, font_size_hook=font_size_hook,
                            font_size_feature=font_size_feature,
                            feature_duration=feature_duration,
                            slide_duration=slide_duration, y_offset=y_off)
        filters.append(f)

    enc_args = get_ffmpeg_encoder_args(crf=crf, preset=preset)
    proc = subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(src), "-vf", ",".join(filters),
         "-r", str(fps), *enc_args, "-pix_fmt", "yuv420p", "-c:a", "copy",
         "-movflags", "+faststart", str(dst)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise OverlayError(f"FFmpeg drawtext failed:\n{proc.stderr.strip()}")


def _overlay_moviepy(
    *, src: Path, dst: Path, events: Sequence[TextEventMakeViral], font_path: Path,
    font_size_hook: int, font_size_feature: int, feature_duration: float,
    slide_duration: float, fps: int, crf: int, preset: str,
) -> None:
    base = VideoFileClip(str(src))
    overlays: list[ImageClip] = []
    tmp_imgs: list[Path] = []

    try:
        tmp_dir = Path(tempfile.mkdtemp(prefix="overlay_"))
        
        # Sort events by start time to make stacking easier
        sorted_events = sorted(events, key=lambda e: e.start if e.effect == "feature" else 0.0)
        
        for ev in sorted_events:
            if ev.effect == "hook":
                img = render_text_img(text=ev.text, font_path=font_path,
                                       font_size=font_size_hook,
                                       max_width=int(base.w * 0.86),
                                       effect="hook")
                p = tmp_dir / f"hook_{len(tmp_imgs):03d}.png"
                img.save(str(p))
                tmp_imgs.append(p)
                clip = ImageClip(str(p), transparent=True)

                slam_dur = 0.25

                def slam_scale(t, sd=slam_dur):
                    if t < sd:
                        progress = t / sd
                        return 2.5 - 1.5 * progress
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
            img = render_text_img(text=ev.text, font_path=font_path,
                                   font_size=font_size_feature,
                                   max_width=int(base.w * 0.84),
                                   effect="feature")
            p = tmp_dir / f"feat_{len(tmp_imgs):03d}.png"
            img.save(str(p))
            tmp_imgs.append(p)
            clip = ImageClip(str(p), transparent=True)
            clip = clip.rotate(-3.5, expand=True)

            dur = min(max(0.2, feature_duration), base.duration - start)
            
            # Vertical stacking logic for concurrent features
            concurrent_features = 0
            for o in overlays:
                if (getattr(o, "is_feature", False) and 
                    not (start >= o.start + o.duration or start + dur <= o.start)):
                    concurrent_features += 1
            
            # Offset Y by 80px for each concurrent feature
            y_offset = concurrent_features * 85
            y_pos = int(base.h * 0.72 - clip.h / 2) + y_offset
            
            # Clamp Y-pos to stay within visible area
            if y_pos > base.h * 0.92:
                y_pos = int(base.h * 0.72 - clip.h / 2) # Fallback to original if too many
            
            tx = int(base.w * 0.08)
            entry = max(0.12, slide_duration)

            def motion(t, sx=start, d=entry, tgt=tx, tw=clip.w, yy=y_pos):
                if t < sx:
                    return (-tw - 80.0, float(yy))
                if t < sx + d:
                    p_ = (t - sx) / d
                    s_val = 1.70158
                    p_rev = p_ - 1.0
                    ease = 1.0 + p_rev * p_rev * ((s_val + 1) * p_rev + s_val)
                    x = (-tw - 80.0) + (tgt + tw + 80.0) * ease
                    return (x, float(yy))
                return (float(tgt), float(yy))

            final_clip = clip.set_start(start).set_duration(dur).set_position(motion)
            final_clip.is_feature = True
            overlays.append(final_clip)

        comp = CompositeVideoClip([base, *overlays], size=base.size).set_duration(base.duration)
        hw_codec = detect_ffmpeg_hw_encoder()
        write_kwargs = {
            "fps": fps,
            "codec": hw_codec,
            "audio_codec": "aac",
            "threads": max(1, (os.cpu_count() or 4) // 2),
            "verbose": False,
            "logger": None,
        }
        if hw_codec == "h264_nvenc":
            write_kwargs["ffmpeg_params"] = [
                "-preset", "p4", "-rc", "vbr", "-cq", str(crf), "-movflags", "+faststart"
            ]
        elif hw_codec == "h264_videotoolbox":
            write_kwargs["ffmpeg_params"] = ["-movflags", "+faststart"]
        else:
            write_kwargs["preset"] = preset
            write_kwargs["ffmpeg_params"] = ["-crf", str(crf), "-movflags", "+faststart"]
            
        comp.write_videofile(str(dst), **write_kwargs)
    except Exception as exc:
        raise OverlayError(f"MoviePy overlay failed: {exc}") from exc
    finally:
        for c in overlays: c.close()
        base.close()
        for ip in tmp_imgs:
            if ip.exists(): ip.unlink()
        if "tmp_dir" in locals() and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


def overlay_text_make_viral(
    input_video: Union[str, Path],
    output_video: Union[str, Path],
    events: Sequence[Union[dict[str, Any], Sequence[Any]]],
    *,
    font_path: Union[str, Path] | None = None,
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

    src = Path(input_video).resolve()
    dst = Path(output_video).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        raise FileNotFoundError(f"Input video not found: {src}")

    font = resolve_font(font_path)
    parsed = [parse_make_viral_event(e) for e in events]
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
