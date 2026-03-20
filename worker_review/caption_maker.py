#!/usr/bin/env python3
"""
caption_maker.py — Hormozi-Style Auto Caption Generator
=========================================================
Workflow:
  1. WhisperX forced alignment  → word-level timestamps
     (Uses your existing script text — NO re-transcription, NO spelling errors)
  2. Smart chunking             → max 3 words, break on punctuation
  3. ASS file generation        → Pop-in animation + neon-yellow keyword highlights
  4. FFmpeg hard-burn           → H.264 output with audio copy

Usage (standalone CLI):
    python caption_maker.py \\
        --audio  raw/vo_58s.mp3 \\
        --script raw/vo_58s.txt \\
        --video  output/yonex_astrox_lite_45i_review_raw.mp4 \\
        --output output/yonex_astrox_lite_45i_review_captioned.mp4

Usage (module):
    from caption_maker import CaptionMaker
    maker = CaptionMaker(highlight_words=["ASTROX", "SMASH"])
    ass   = maker.generate_ass("raw/vo_58s.mp3", "raw/vo_58s.txt", "output/vo.ass")
    maker.burn("output/raw.mp4", ass, "output/final.mp4")

Integration helper (called by video_builder):
    from caption_maker import make_caption_ass, burn_caption_to_video
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("CaptionMaker")

# ── ASS color constants  (format: &HAABBGGRR) ────────────────────────────────
_WHITE  = "&H00FFFFFF"   # opaque white
_YELLOW = "&H0000FFFF"   # neon yellow (R=FF G=FF B=00)
_BLACK  = "&H00000000"   # opaque black  (for outline)

# ── Pop-in: scale 120% → 100% in first 200 ms (Hormozi style) ────────────────
_POP_IN = r"{\t(0,100,\fscx120\fscy120)\t(100,200,\fscx100\fscy100)}"

# ── ASS Header ─────────────────────────────────────────────────────────────────
# Alignment 2 = bottom-center, MarginV 350 = safe zone above TikTok bottom UI
_ASS_HEADER = (
    "[Script Info]\n"
    "ScriptType: v4.00+\n"
    "PlayResX: 1080\n"
    "PlayResY: 1920\n"
    "ScaledBorderAndShadow: yes\n"
    "YCbCr Matrix: None\n"
    "\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
    " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
    " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
    " Alignment, MarginL, MarginR, MarginV, Encoding\n"
    f"Style: Default,Arial,90,{_WHITE},{_WHITE},{_BLACK},&H00000000,"
    "-1,0,0,0,100,100,0,0,1,8,0,2,0,0,350,1\n"
    "\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)

# ── Default highlight keywords (Vietnamese badminton-review context) ──────────
try:
    _HIGHLIGHT_WORDS_FILE = Path(__file__).parent / "highlight_words.json"
    with open(_HIGHLIGHT_WORDS_FILE, "r", encoding="utf-8") as _f:
        DEFAULT_HIGHLIGHT_WORDS: List[str] = json.load(_f)
except Exception as e:
    logger.warning(f"Could not load {_HIGHLIGHT_WORDS_FILE}: {e}")
    DEFAULT_HIGHLIGHT_WORDS: List[str] = [
        "MUA", "VỢT", "SAI", "MẤT",
        "ASTROX", "LITE", "45I", "YONEX",
        "RUNG TAY", "LỆCH KHUNG", "LINH HOẠT", "ỔN ĐỊNH",
        "CHỐNG SỐC", "PHONG TRÀO", "SMASH", "MIỄN PHÍ",
        "PART 2", "GIẢ", "THẬT", "CẢNH BÁO",
    ]

# ── Punctuation that forces a chunk break ─────────────────────────────────────
_BREAK_RE = re.compile(r"[,\.?!;:\u2026\u201c\u201d]")


# ═══════════════════════════════════════════════════════════════════════════════
# ASS helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _secs_to_ass(t: float) -> str:
    """Float seconds → ASS timestamp  H:MM:SS.cc"""
    t  = max(0.0, t)
    cs = round(t * 100)
    h,  cs = divmod(cs, 360_000)
    m,  cs = divmod(cs, 6_000)
    s,  cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _build_dialogue_text(words: List[str], highlight_words: List[str]) -> str:
    """
    Build ASS event text:
      • Pop-in animation tag prepended
      • White base color
      • Keywords wrapped in neon-yellow color override
    """
    white_tag  = rf"{{\c{_WHITE}&}}"
    yellow_tag = rf"{{\c{_YELLOW}&}}"

    kw_upper = [w.upper() for w in highlight_words]
    parts: List[str] = []
    for word in words:
        if word.upper() in kw_upper:
            parts.append(yellow_tag + word + white_tag)
        else:
            parts.append(word)

    return _POP_IN + white_tag + " ".join(parts)


def _has_ffmpeg_ass_filter() -> bool:
    """Return True if local FFmpeg supports the ass video filter."""
    try:
        out = subprocess.check_output(
            ["ffmpeg", "-filters"],
            stderr=subprocess.STDOUT,
            text=True,
        )
        return bool(re.search(r"^\s+\.\.\s+ass\b", out, re.MULTILINE))
    except Exception:
        return False





# ═══════════════════════════════════════════════════════════════════════════════
# CaptionMaker
# ═══════════════════════════════════════════════════════════════════════════════

class CaptionMaker:
    """
    Hormozi-style word-level caption generator backed by WhisperX forced alignment.

    Parameters
    ----------
    highlight_words     : words/phrases to colour neon-yellow
    max_words_per_chunk : chunk size cap (default 3)
    language            : BCP-47 code passed to WhisperX  (default "vi")
    device              : torch device — "cpu", "cuda", or "mps"
    """

    def __init__(
        self,
        highlight_words: Optional[List[str]] = None,
        max_words_per_chunk: int = 3,
        language: str = "vi",
        device: str = "cpu",
    ) -> None:
        self.highlight_words = highlight_words if highlight_words is not None else DEFAULT_HIGHLIGHT_WORDS
        self.max_words = max_words_per_chunk
        self.language  = language
        self.device    = device

    # ── Step 1: WhisperX forced alignment ─────────────────────────────────────

    def _forced_align(self, audio_path: str, script_text: str) -> List[Dict]:
        """
        Align *script_text* against *audio_path* using WhisperX forced alignment.

        We deliberately do NOT re-transcribe (avoids hallucination / wrong spelling).
        Instead we provide the ground-truth script as a single transcript segment
        and let whisperx.align() map each word to its exact timestamp in the audio.

        Returns
        -------
        list of {"word": str, "start": float, "end": float}
        """
        try:
            import whisperx          # type: ignore
        except ImportError:
            raise RuntimeError(
                "whisperx is not installed.\n"
                "  pip install whisperx\n"
                "See https://github.com/m-bain/whisperX for details."
            )

        logger.info(f"Loading audio  : {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # Estimate audio duration (samples / sample_rate = seconds).
        # whisperx.load_audio returns a 1-D numpy array at 16 kHz.
        audio_duration = float(len(audio)) / 16_000.0
        logger.info(f"Audio duration : {audio_duration:.1f}s")

        logger.info(f"Loading alignment model  (lang={self.language}, device={self.device})")
        
        # Use Vietnamese-specific Wav2Vec2 model for accurate forced alignment
        model_kwargs = {"language_code": self.language, "device": self.device}
        if self.language == "vi":
            model_kwargs["model_name"] = "nguyenvulebinh/wav2vec2-base-vietnamese-250h"
        
        model_a, metadata = whisperx.load_align_model(**model_kwargs)

        # Split script into sentence-level segments with proportional timestamps.
        # Feeding one giant segment causes CTC alignment to compress all words
        # into the first few seconds. Sentence-level segments give the aligner
        # proper time-windows and produce accurate word timestamps.
        transcript_segments = self._split_script_to_segments(
            script_text, audio_duration
        )
        logger.info(f"  {len(transcript_segments)} text segments prepared for alignment")

        logger.info("Running forced alignment …")
        result = whisperx.align(
            transcript_segments,
            model_a,
            metadata,
            audio,
            self.device,
            return_char_alignments=False,
        )

        word_list: List[Dict] = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                word_text = w.get("word", "").strip()
                if not word_text:
                    continue
                word_list.append({
                    "word":  word_text,
                    "start": float(w.get("start", 0.0)),
                    "end":   float(w.get("end", 0.0)),
                })

        logger.info(f"  → {len(word_list)} words aligned")

        # Linear-interpolate any words that came back without timestamps
        word_list = self._fix_missing_timestamps(word_list, audio_duration)
        return word_list

    @staticmethod
    def _split_script_to_segments(
        script_text: str, audio_duration: float
    ) -> List[Dict]:
        """
        Split the full script into sentence-level segments with proportional
        time estimates.  WhisperX align() works much better when each segment
        covers a short sentence rather than the entire transcript.

        Splitting strategy:
          • Split on sentence-ending punctuation (.  ?  !  …)
          • Each sentence's time window is proportional to its word count
          • Small overlap (0.5 s) between windows helps alignment accuracy
        """
        # Split on sentence boundaries while keeping the delimiter
        raw_sentences = re.split(r'(?<=[.?!…])\s+', script_text.strip())
        # Filter empty
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        if not sentences:
            return [{"text": script_text, "start": 0.0, "end": audio_duration}]

        # Compute word counts to proportionally distribute time
        word_counts = [len(s.split()) for s in sentences]
        total_words = sum(word_counts)
        if total_words == 0:
            return [{"text": script_text, "start": 0.0, "end": audio_duration}]

        segments: List[Dict] = []
        cursor = 0.0
        for sent, wc in zip(sentences, word_counts):
            # Proportional duration based on word count
            seg_dur = (wc / total_words) * audio_duration
            seg_end = min(cursor + seg_dur, audio_duration)

            # Add small overlap to help alignment at boundaries
            padded_start = max(0.0, cursor - 0.3)
            padded_end   = min(audio_duration, seg_end + 0.3)

            segments.append({
                "text":  sent,
                "start": padded_start,
                "end":   padded_end,
            })
            cursor = seg_end

        return segments

    @staticmethod
    def _fix_missing_timestamps(
        words: List[Dict], total_duration: float
    ) -> List[Dict]:
        """Fill in 0-duration or missing timestamps by linear interpolation."""
        if not words:
            return words

        # Mark words that need fixing (start == end == 0 after the first word)
        for i, w in enumerate(words):
            if w["start"] == 0.0 and w["end"] == 0.0 and i > 0:
                w["_missing"] = True

        # Walk through and interpolate gaps
        n = len(words)
        i = 0
        while i < n:
            if words[i].get("_missing"):
                # Find next word with a valid timestamp
                j = i + 1
                while j < n and words[j].get("_missing"):
                    j += 1
                t_start = words[i - 1]["end"] if i > 0 else 0.0
                t_end   = words[j]["start"] if j < n else total_duration
                span    = j - i
                for k in range(span):
                    frac = (k + 1) / (span + 1)
                    words[i + k]["start"] = t_start + frac * (t_end - t_start) - 0.05
                    words[i + k]["end"]   = t_start + frac * (t_end - t_start) + 0.05
                    del words[i + k]["_missing"]
                i = j
            else:
                words[i].pop("_missing", None)
                i += 1

        return words

    # ── Step 2: Smart chunking ────────────────────────────────────────────────

    def _smart_chunk(self, word_list: List[Dict]) -> List[Dict]:
        """
        Group word-level timestamps into display chunks.

        Rules (in priority order):
          1. Break immediately when a word ends with punctuation (,  .  ?  !  ;  :  …)
          2. Break when chunk reaches `self.max_words` words
          3. Everything else goes into the current chunk

        Returns list of {"words": [str,…], "start": float, "end": float}
        """
        chunks: List[Dict] = []
        current_words: List[str] = []
        current_start: Optional[float] = None
        current_end: float = 0.0

        def _flush() -> None:
            nonlocal current_words, current_start, current_end
            if current_words:
                chunks.append({
                    "words": list(current_words),
                    "start": current_start,
                    "end":   current_end,
                })
            current_words.clear()
            current_start = None
            current_end   = 0.0

        for w in word_list:
            word = w["word"]
            if not word:
                continue

            if current_start is None:
                current_start = w["start"]

            current_words.append(word)
            current_end = w["end"]

            ends_with_punct = bool(_BREAK_RE.search(word))
            if len(current_words) >= self.max_words or ends_with_punct:
                _flush()

        _flush()  # flush any trailing words
        return chunks

    # ── Step 3: ASS generation ────────────────────────────────────────────────

    def generate_ass(
        self,
        audio_path: str,
        script_path: str,
        ass_path: str,
    ) -> str:
        """
        Full pipeline: align → chunk → write ASS file.

        Parameters
        ----------
        audio_path  : voiceover MP3/WAV
        script_path : .txt file containing the ground-truth script
        ass_path    : destination .ass file path

        Returns
        -------
        ass_path (for chaining)
        """
        script_text = Path(script_path).read_text(encoding="utf-8").strip()
        if not script_text:
            raise ValueError(f"Script file is empty: {script_path}")

        word_list = self._forced_align(audio_path, script_text)
        if not word_list:
            raise RuntimeError(
                "Forced alignment returned no words. "
                "Verify that the audio and script match."
            )

        chunks = self._smart_chunk(word_list)
        logger.info(f"  → {len(chunks)} caption chunks")

        dialogues: List[str] = []
        for chunk in chunks:
            t0   = _secs_to_ass(chunk["start"])
            t1   = _secs_to_ass(chunk["end"])
            body = _build_dialogue_text(chunk["words"], self.highlight_words)
            dialogues.append(f"Dialogue: 0,{t0},{t1},Default,,0,0,0,,{body}")

        Path(ass_path).write_text(
            _ASS_HEADER + "\n".join(dialogues) + "\n",
            encoding="utf-8-sig",   # BOM  — required for libass compatibility
        )
        logger.info(f"  .ass written : {ass_path}  ({len(chunks)} events)")
        return ass_path

    # ── Step 4: FFmpeg hard-burn ──────────────────────────────────────────────

    def burn(self, video_in: str, ass_file: str, video_out: str) -> str:
        """
        Hard-burn the ASS caption file into a video using FFmpeg (libass).

        Requires: FFmpeg compiled with libass filter support.
        Uses:
          -vf "ass=<path>"   — libass renderer
          -c:v libx264       — H.264
          -preset fast       — good speed / quality balance
          -c:a copy          — preserve original audio exactly

        Raises
        ------
        RuntimeError
            If FFmpeg lacks libass support

        Returns
        -------
        video_out path
        """
        abs_ass = str(Path(ass_file).resolve())
        has_ass = _has_ffmpeg_ass_filter()

        if not has_ass:
            raise RuntimeError(
                "FFmpeg trên máy chưa được cài đặt module libass.\n"
                "Vui lòng chạy lệnh sau để cải thiện:\n"
                "  • Mac (Homebrew):  brew install ffmpeg\n"
                "  • Linux (Ubuntu):  sudo apt-get install ffmpeg\n"
                "  • Windows:         Tải ffmpeg từ ffmpeg.org và đảm bảo libass được bật.\n"
                "\nLuôn fallback hoàn toàn không hỗ trợ — chỉ dùng FFmpeg libass!"
            )

        # On Windows colons in drive letters must be escaped for libass
        if os.name == "nt":
            filter_path = abs_ass.replace("\\", "/").replace(":", "\\:")
        else:
            filter_path = abs_ass

        cmd = [
            "ffmpeg", "-y",
            "-i", video_in,
            "-vf", f"ass={filter_path}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            video_out,
        ]
        logger.info(f"FFmpeg burn: {Path(video_in).name} → {Path(video_out).name}")
        logger.info(f"  cmd: {' '.join(cmd)}")

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            logger.error("FFmpeg stderr (last 3000 chars):\n" + proc.stderr[-3000:])
            raise RuntimeError(f"FFmpeg caption burn failed (exit {proc.returncode})")

        size_mb = Path(video_out).stat().st_size / 1_024 / 1_024
        logger.info(f"  ✓ Burned → {video_out}  ({size_mb:.1f} MB)")
        return video_out



# ═══════════════════════════════════════════════════════════════════════════════
# Convenience wrappers  (called by video_builder)
# ═══════════════════════════════════════════════════════════════════════════════

def make_caption_ass(
    audio_path: str,
    script_path: str,
    ass_path: str,
    highlight_words: Optional[List[str]] = None,
    language: str = "vi",
    device: str = "cpu",
) -> str:
    """Align + chunk + write ASS.  Returns ass_path."""
    maker = CaptionMaker(
        highlight_words=highlight_words,
        language=language,
        device=device,
    )
    return maker.generate_ass(audio_path, script_path, ass_path)


def burn_caption_to_video(video_in: str, ass_file: str, video_out: str) -> str:
    """Hard-burn captions into video.  Returns video_out."""
    return CaptionMaker().burn(video_in, ass_file, video_out)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Hormozi-style Hormozi caption generator via WhisperX forced alignment"
    )
    p.add_argument("--audio",    required=True,  help="Voiceover audio file (MP3/WAV/…)")
    p.add_argument("--script",   required=True,  help="Ground-truth script .txt file")
    p.add_argument("--video",    default=None,   help="Input MP4 to burn captions into")
    p.add_argument("--output",   default=None,   help="Output MP4 path (requires --video)")
    p.add_argument("--ass",      default=None,   help="Output .ass path  (default: next to audio)")
    p.add_argument("--lang",     default="vi",   help="Language code (default: vi)")
    p.add_argument("--device",   default="cpu",  help="Torch device: cpu | cuda | mps")
    p.add_argument(
        "--keywords", nargs="*", default=None,
        help="Custom highlight keywords (space-separated, e.g. ASTROX SMASH)"
    )
    return p.parse_args()


def main() -> None:
    args   = _parse_args()
    ass_path = args.ass or str(Path(args.audio).with_suffix(".ass"))

    maker = CaptionMaker(
        highlight_words=args.keywords,
        language=args.lang,
        device=args.device,
    )
    maker.generate_ass(args.audio, args.script, ass_path)
    logger.info(f"ASS file : {ass_path}")

    if args.video and args.output:
        maker.burn(args.video, ass_path, args.output)
        logger.info(f"Done → {args.output}")
    elif args.video and not args.output:
        logger.warning("--video provided but --output is missing; skipping burn step.")


if __name__ == "__main__":
    main()
