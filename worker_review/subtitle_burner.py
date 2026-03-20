#!/usr/bin/env python3
"""
subtitle_burner.py — ASS Subtitle Generation + Hard-burn
==========================================================
Two duties:

  1. generate_ass()  — Produce a .ass (Advanced SubStation Alpha) file with:
       • PlayResX/Y: 1080×1920  (TikTok / Reels format)
       • Font: Montserrat Bold (falls back to Arial Bold / Arial)
       • Fontsize 90, Alignment 5 (center), MarginV 900
       • Outline: black 8px, no shadow
       • Pop-in: {\t(0,100,\fscx130\fscy130)\t(100,200,\fscx100\fscy100)}
       • Normal text    : white   (&H00FFFFFF)
       • Highlight kw   : neon yellow (&H0000FFFF, RGB 255,255,0)

  2. burn()  — hard-burn subtitles into MP4.
       • PRIMARY  path (needs libass): FFmpeg -vf ass=<path>  -c:a copy
       • FALLBACK path (no libass)  : moviepy + PIL with animated pop-in

Usage (standalone):
    python subtitle_burner.py                     # uses ./input.json
    python subtitle_burner.py path/to/config.json

Usage (module):
    from subtitle_burner import SubtitleBurner
    SubtitleBurner().process(entries, "raw.mp4", "final.mp4")
"""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SubtitleBurner")

# ── ASS color constants  (format: &HAABBGGRR) ───────────────────────────────────
_WHITE  = "&H00FFFFFF"   # opaque white
_YELLOW = "&H0000FFFF"   # neon yellow: R=FF G=FF B=00  → AABBGGRR = 00 00 FF FF
_BLACK  = "&H00000000"   # opaque black (outline)

# ── Pop-in animation tag (0→100ms: 130%, 100→200ms: 100%) ──────────────────
_POP_IN = r"{\t(0,100,\fscx130\fscy130)\t(100,200,\fscx100\fscy100)}"

# ── ASS Header template ─────────────────────────────────────────────────────
_ASS_HEADER_TMPL = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},90,{white},{white},{black},&H00000000,-1,0,0,0,100,100,0,0,1,8,0,5,0,0,900,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# ── PIL rendering constants (fallback path) ─────────────────────────────────
_PIL_WHITE  = (255, 255, 255)
_PIL_YELLOW = (255, 255,   0)   # neon yellow
_PIL_BLACK  = (  0,   0,   0)
_PIL_OUTLINE_W = 8              # match ASS Outline: 8
_PIL_FONTSIZE  = 90
_TEXT_CENTER_Y = 700            # vertical center of text block (px from top)
                                # ~36 % of 1920 — safe zone above TikTok UI
_MAX_TEXT_WIDTH_RATIO = 0.86    # keep text within safe horizontal region
_MIN_FONTSIZE = 58


# ──────────────────────────  ASS helpers  ──────────────────────────

def _secs_to_ass(t: float) -> str:
    """Float seconds → ASS time string H:MM:SS.cc"""
    t  = max(0.0, t)
    cs = round(t * 100)
    h,  cs = divmod(cs, 360000)
    m,  cs = divmod(cs, 6000)
    s,  cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _tagged_text(text: str, highlight_words: List[str]) -> str:
    """Build an ASS dialogue text with pop-in animation + keyword coloring."""
    WHITE_TAG  = rf"{{\c{_WHITE}&}}"
    YELLOW_TAG = rf"{{\c{_YELLOW}&}}"
    prefix     = _POP_IN + WHITE_TAG

    if not highlight_words:
        return prefix + text.replace("\n", r"\N")

    sorted_kw = sorted(highlight_words, key=len, reverse=True)
    pattern   = "|".join(re.escape(w) for w in sorted_kw)

    tagged_lines = []
    for line in text.split("\n"):
        parts = re.split(f"({pattern})", line, flags=re.IGNORECASE)
        out   = ""
        for part in parts:
            if re.fullmatch(pattern, part, flags=re.IGNORECASE):
                out += YELLOW_TAG + part + WHITE_TAG
            else:
                out += part
        tagged_lines.append(out)

    return prefix + r"\N".join(tagged_lines)


# ───────────────────────  PIL / moviepy helpers  ───────────────────────

def _load_pil_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/Library/Fonts/Montserrat-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _color_runs(line: str, pattern: Optional[str]):
    """Return list of (text, is_highlight) tuples for one line."""
    if not pattern:
        return [(line, False)]
    parts = re.split(f"({pattern})", line, flags=re.IGNORECASE)
    return [
        (p, bool(re.fullmatch(pattern, p, flags=re.IGNORECASE)))
        for p in parts if p
    ]


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _split_long_word(
    word: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> List[str]:
    """Split a very long token into chunks that fit max_width."""
    chunks: List[str] = []
    current = ""
    for ch in word:
        candidate = current + ch
        if current and _text_width(draw, candidate, font) > max_width:
            chunks.append(current)
            current = ch
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _wrap_text_lines(
    text: str,
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> List[str]:
    """Wrap text into multiple lines so each line fits the target width."""
    wrapped: List[str] = []

    for raw_line in text.split("\n"):
        if not raw_line.strip():
            wrapped.append("")
            continue

        words = raw_line.split()
        line_words: List[str] = []

        for word in words:
            # Handle a single token that is longer than the full line width.
            if _text_width(draw, word, font) > max_width:
                if line_words:
                    wrapped.append(" ".join(line_words))
                    line_words = []
                parts = _split_long_word(word, draw, font, max_width)
                wrapped.extend(parts[:-1])
                line_words = [parts[-1]] if parts else []
                continue

            candidate = " ".join(line_words + [word]) if line_words else word
            if line_words and _text_width(draw, candidate, font) > max_width:
                wrapped.append(" ".join(line_words))
                line_words = [word]
            else:
                line_words.append(word)

        if line_words:
            wrapped.append(" ".join(line_words))

    return wrapped


def _fit_text_lines(text: str, W: int, fontsize: int):
    """Choose a font size and wrapped lines that fit the frame width."""
    max_width = int(W * _MAX_TEXT_WIDTH_RATIO)
    measure_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(measure_img)

    size = fontsize
    best_font = _load_pil_font(size)
    best_lines = _wrap_text_lines(text, draw, best_font, max_width)

    while size >= _MIN_FONTSIZE:
        font = _load_pil_font(size)
        lines = _wrap_text_lines(text, draw, font, max_width)
        widest = max((_text_width(draw, ln, font) for ln in lines if ln.strip()), default=0)
        best_font, best_lines = font, lines
        if widest <= max_width:
            break
        size -= 4

    return best_font, best_lines


def _prepare_text_for_ass(text: str, W: int = 1080, fontsize: int = _PIL_FONTSIZE) -> str:
    """Pre-wrap subtitle text so ASS and PIL paths share the same line breaks."""
    _, lines = _fit_text_lines(text, W, fontsize)
    return "\n".join(lines)


def _render_subtitle_frame(
    text: str,
    highlight_words: List[str],
    W: int,
    H: int,
    fontsize: int = _PIL_FONTSIZE,
) -> np.ndarray:
    """
    Render subtitle text onto a transparent RGBA canvas.
    Returns numpy array (H, W, 4).
    """
    img   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(img)
    font, lines = _fit_text_lines(text, W, fontsize)

    kw_pattern = None
    if highlight_words:
        sorted_kw  = sorted(highlight_words, key=len, reverse=True)
        kw_pattern = "|".join(re.escape(w) for w in sorted_kw)

    # Measure line heights (handle blank spacer lines)
    bb_h = draw.textbbox((0, 0), "Ag", font=font)
    font_h = bb_h[3] - bb_h[1]
    line_h  = font_h + 14
    blank_h = max(18, font_h // 2)

    # Count rendered lines to vertically center the block
    rendered_count = sum(1 for l in lines if l.strip())
    block_h = rendered_count * line_h + (len(lines) - rendered_count) * blank_h
    y = _TEXT_CENTER_Y - block_h // 2

    for line in lines:
        if not line.strip():
            y += blank_h
            continue

        runs = _color_runs(line, kw_pattern)

        # Measure entire line width to center horizontally
        total_w = 0
        for part, _ in runs:
            total_w += _text_width(draw, part, font)
        x = (W - total_w) // 2

        for part, is_hl in runs:
            color = _PIL_YELLOW if is_hl else _PIL_WHITE
            # PIL native stroke avoids manual loop buffer overflow with Unicode glyphs
            draw.text(
                (x, y), part, font=font, fill=color,
                stroke_width=_PIL_OUTLINE_W,
                stroke_fill=_PIL_BLACK,
            )
            x += _text_width(draw, part, font)

        y += line_h

    return np.array(img)


def _make_popin_clip(img_arr: np.ndarray, duration: float, W: int, H: int):
    """
    Wrap a rendered subtitle frame in a moviepy clip with
    a 130% -> 100% ease-out scale pop-in over the first 0.2 s.
    Splits RGBA into RGB base + float mask to avoid moviepy buffer errors.
    """
    from moviepy.editor import ImageClip

    POPIN_DUR = 0.2
    rgb   = img_arr[:, :, :3]                        # (H, W, 3) uint8
    alpha = img_arr[:, :, 3].astype(float) / 255.0  # (H, W)    float 0-1

    base = ImageClip(rgb).set_duration(duration)
    mask = ImageClip(alpha, ismask=True).set_duration(duration)

    def _anim_rgb(get_frame, t):
        frame = get_frame(t)          # (H, W, 3) uint8 RGB
        if t >= POPIN_DUR:
            return frame
        progress = t / POPIN_DUR
        eased    = 1.0 - (1.0 - progress) ** 2
        scale    = 1.3 - 0.3 * eased
        sw = max(1, round(W * scale))
        sh = max(1, round(H * scale))
        arr = np.array(Image.fromarray(frame, "RGB").resize((sw, sh), Image.LANCZOS))
        if scale > 1.0:
            # Scaled image is bigger — center-crop to canvas size
            x0, y0 = (sw - W) // 2, (sh - H) // 2
            return arr[y0:y0 + H, x0:x0 + W]
        else:
            canvas = np.zeros((H, W, 3), dtype=np.uint8)
            x0, y0 = (W - sw) // 2, (H - sh) // 2
            canvas[y0:y0 + sh, x0:x0 + sw] = arr
            return canvas

    def _anim_mask(get_frame, t):
        frame = get_frame(t)          # (H, W) float 0-1
        if t >= POPIN_DUR:
            return frame
        progress = t / POPIN_DUR
        eased    = 1.0 - (1.0 - progress) ** 2
        scale    = 1.3 - 0.3 * eased
        sw = max(1, round(W * scale))
        sh = max(1, round(H * scale))
        u8  = (frame * 255).astype(np.uint8)
        arr = np.array(Image.fromarray(u8, "L").resize((sw, sh), Image.LANCZOS)).astype(float) / 255.0
        if scale > 1.0:
            x0, y0 = (sw - W) // 2, (sh - H) // 2
            return arr[y0:y0 + H, x0:x0 + W]
        else:
            canvas = np.zeros((H, W), dtype=float)
            x0, y0 = (W - sw) // 2, (H - sh) // 2
            canvas[y0:y0 + sh, x0:x0 + sw] = arr
            return canvas

    return base.fl(_anim_rgb).set_mask(mask.fl(_anim_mask))


# ────────────────────────  SubtitleBurner class  ────────────────────────

class SubtitleBurner:
    """
    Generates .ass subtitle files and hard-burns them into MP4.

    Entry-point dict schema (one per subtitle):
    {
        "start":           float,       # start time on the output video (seconds)
        "end":             float,       # end time on the output video (seconds)
        "text":            str,         # display text (\\n = newline)
        "highlight_words": list[str],   # optional — colored neon yellow
    }
    """

    _FONT_PREFERENCE = ["Montserrat", "Montserrat Bold", "Arial Bold", "Arial", "Helvetica"]

    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = config or {}

    # ── Font detection (for ASS header) ────────────────────────────────────

    def _detect_font(self) -> str:
        try:
            raw  = subprocess.check_output(
                ["fc-list", "--format=%{family}\n"],
                text=True, stderr=subprocess.DEVNULL,
            )
            avail = {l.strip().split(",")[0].strip() for l in raw.splitlines() if l.strip()}
            for name in self._FONT_PREFERENCE:
                if name in avail:
                    return name
        except Exception:
            pass
        pairs = [
            ("/Library/Fonts/Montserrat-Bold.ttf",                "Montserrat"),
            ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "Arial Bold"),
            ("/System/Library/Fonts/Helvetica.ttc",               "Helvetica"),
        ]
        for path, name in pairs:
            if os.path.exists(path):
                return name
        return "Arial"

    # ── FFmpeg libass detection ──────────────────────────────────────────────

    @staticmethod
    def _has_libass() -> bool:
        """Return True if the current FFmpeg is compiled with the 'ass' filter."""
        try:
            out = subprocess.check_output(
                ["ffmpeg", "-filters"], text=True, stderr=subprocess.STDOUT
            )
            # ass filter appears as:  " .. ass   V->V  ..."
            return bool(re.search(r"^\s+\.\. ass\b", out, re.MULTILINE))
        except Exception:
            return False

    # ── ASS file generation ──────────────────────────────────────────────────

    def generate_ass(self, entries: List[Dict], ass_path: str) -> str:
        """
        Write the .ass subtitle file.

        Parameters
        ----------
        entries  : list of subtitle dicts
        ass_path : destination .ass path

        Returns  : ass_path
        """
        font   = self._detect_font()
        header = _ASS_HEADER_TMPL.format(font=font, white=_WHITE, black=_BLACK)

        dialogues = []
        for e in entries:
            t0   = _secs_to_ass(e["start"])
            t1   = _secs_to_ass(e["end"])
            wrapped_text = _prepare_text_for_ass(e["text"])
            body = _tagged_text(wrapped_text, e.get("highlight_words", []))
            dialogues.append(f"Dialogue: 0,{t0},{t1},Default,,0,0,0,,{body}")

        Path(ass_path).write_text(
            header + "\n".join(dialogues) + "\n",
            encoding="utf-8-sig",   # BOM — libass compatibility
        )
        logger.info(f"  .ass written: {ass_path}  ({len(entries)} lines)")
        return ass_path

    # ── PRIMARY burn path: FFmpeg -vf ass (needs libass) ─────────────────────

    def _burn_ffmpeg_ass(
        self, input_mp4: str, ass_path: str, output_mp4: str
    ) -> str:
        abs_ass     = str(Path(ass_path).resolve())
        filter_path = abs_ass.replace("\\", "/")
        if os.name == "nt":
            filter_path = filter_path.replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", input_mp4,
            "-vf", f"ass={filter_path}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            output_mp4,
        ]
        logger.info(f"  FFmpeg ASS burn: {Path(input_mp4).name} → {Path(output_mp4).name}")
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if proc.returncode != 0:
            logger.error("FFmpeg stderr:\n" + proc.stderr[-3000:])
            raise RuntimeError(f"FFmpeg burn failed (exit {proc.returncode})")

        size_mb = Path(output_mp4).stat().st_size / 1024 / 1024
        logger.info(f"  ✓ Burned (FFmpeg ASS) → {output_mp4}  ({size_mb:.1f} MB)")
        return output_mp4

    # ── FALLBACK burn path: moviepy + PIL (no libass needed) ────────────────

    def _burn_via_moviepy(
        self, entries: List[Dict], input_mp4: str, output_mp4: str
    ) -> str:
        """
        Fallback: use moviepy to composite PIL-rendered subtitle frames
        (with pop-in scale animation) directly onto the raw video.
        Produces identical visual intent to the ASS path.
        """
        from moviepy.editor import VideoFileClip, CompositeVideoClip

        logger.info("  Using moviepy / PIL fallback (libass not found)")
        video = VideoFileClip(input_mp4)
        W, H  = int(video.w), int(video.h)

        text_clips = []
        for entry in entries:
            wrapped_text = _prepare_text_for_ass(entry["text"], W)
            arr = _render_subtitle_frame(
                wrapped_text, entry.get("highlight_words", []), W, H
            )
            tc = _make_popin_clip(arr, entry["end"] - entry["start"], W, H)
            tc = tc.set_start(entry["start"])
            text_clips.append(tc)

        final = CompositeVideoClip([video] + text_clips, size=(W, H))
        final.write_videofile(
            output_mp4,
            fps=video.fps,
            codec="libx264",
            audio_codec="aac",
            preset="fast",
            logger="bar",
        )
        video.close()
        final.close()

        size_mb = Path(output_mp4).stat().st_size / 1024 / 1024
        logger.info(f"  ✓ Burned (moviepy/PIL) → {output_mp4}  ({size_mb:.1f} MB)")
        return output_mp4

    # ── Public API ──────────────────────────────────────────────────────────────

    def burn(self, input_mp4: str, ass_path: str, output_mp4: str) -> str:
        """
        Hard-burn .ass subtitles into MP4.
        Automatically selects FFmpeg-ASS path when libass is available,
        otherwise falls back to moviepy/PIL rendering.
        """
        if self._has_libass():
            return self._burn_ffmpeg_ass(input_mp4, ass_path, output_mp4)
        logger.warning("libass not found in FFmpeg — subtitle_burner will use PIL fallback.")
        logger.warning("To enable ASS: brew install libass && brew reinstall ffmpeg")
        # Fallback requires entries; read them back from the ASS file is complex.
        # process() should call _burn_via_moviepy directly when libass is absent.
        raise RuntimeError(
            "burn() requires entries when libass is not available. Use process() instead."
        )

    def process(
        self,
        entries:    List[Dict],
        input_mp4:  str,
        output_mp4: str,
        ass_path:   Optional[str] = None,
    ) -> str:
        """
        Full pipeline: generate .ass  then  burn into MP4.

        Automatically picks the best available burn method:
          • FFmpeg -vf ass=  (when libass available — faster, ASS-perfect)
          • moviepy + PIL    (universal fallback with pop-in + yellow highlight)

        Parameters
        ----------
        entries     : subtitle dicts  (start, end, text, highlight_words)
        input_mp4   : source MP4 without burned text
        output_mp4  : destination MP4 with hard-burned subtitles
        ass_path    : optional explicit .ass save path

        Returns     : output_mp4 path
        """
        if not ass_path:
            ass_path = str(Path(output_mp4).with_suffix(".ass"))

        logger.info("── SubtitleBurner ──────────────────────────────────")
        self.generate_ass(entries, ass_path)   # always write for reference

        if self._has_libass():
            logger.info("  libass detected — using FFmpeg -vf ass path")
            return self._burn_ffmpeg_ass(input_mp4, ass_path, output_mp4)

        logger.warning("  libass not found   — using moviepy/PIL fallback")
        logger.warning("  Tip: brew install libass && brew reinstall ffmpeg")
        return self._burn_via_moviepy(entries, input_mp4, output_mp4)


# ──────────────────────  Standalone entry point  ──────────────────────

def _load_json(path: str) -> Dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    """
    Standalone:
        python subtitle_burner.py [config.json]

    Reads  output/{project_id}.mp4   (rendered by video_builder.py)
    Writes output/{project_id}_subtitled.mp4
           output/{project_id}.ass
    """
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else "input.json"
    if not os.path.exists(cfg_path):
        logger.error(f"Config not found: {cfg_path}")
        sys.exit(1)

    config   = _load_json(cfg_path)
    base     = Path(cfg_path).resolve().parent
    pid      = config["metadata"]["project_id"]
    src_mp4  = str(base / "output" / f"{pid}.mp4")
    out_mp4  = str(base / "output" / f"{pid}_subtitled.mp4")
    ass_file = str(base / "output" / f"{pid}.ass")

    if not os.path.exists(src_mp4):
        logger.error(f"Source MP4 not found: {src_mp4}")
        logger.error("Run video_builder.py first.")
        sys.exit(1)

    timeline = config.get("timeline_script", [])
    entries  = [
        {
            "start":           seg["time_range"][0],
            "end":             seg["time_range"][1],
            "text":            seg["text_overlay"],
            "highlight_words": seg.get("highlight_words", []),
        }
        for seg in timeline
        if seg.get("text_overlay")
    ]

    if not entries:
        logger.warning("No text_overlay entries found.")
        sys.exit(0)

    SubtitleBurner(config).process(entries, src_mp4, out_mp4, ass_file)
    logger.info(f"\n✓ Subtitled video → {out_mp4}")


if __name__ == "__main__":
    main()

