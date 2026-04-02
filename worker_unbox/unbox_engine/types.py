"""
Data structures, types, and exceptions for the unbox_engine.
"""
from dataclasses import dataclass
from pathlib import Path

# ── Exceptions ──────────────────────────────────────────────────────────────

class FFmpegNotFoundError(RuntimeError):
    pass

class VideoProcessingError(RuntimeError):
    pass

class OverlayError(RuntimeError):
    pass

class UnboxViralError(RuntimeError):
    """Base exception for unbox_viral pipeline."""
    pass


# ── Data Classes (make_viral) ───────────────────────────────────────────────

@dataclass(frozen=True)
class SceneSpec:
    source: Path
    start: float
    duration: float
    order: int

@dataclass(frozen=True)
class VideoTrimInfo:
    source: Path
    duration: float
    trim_start: float
    trim_end: float

@dataclass(frozen=True)
class TextEventMakeViral:
    start: float
    text: str
    effect: str


# ── Data Classes (unbox_viral) ───────────────────────────────────────────────

@dataclass(frozen=True)
class BeatInfo:
    """A single beat drop timestamp."""
    time: float
    strength: float = 1.0

@dataclass
class SegmentInfo:
    """Motion analysis result for a video segment."""
    start: float
    end: float
    motion_score: float
    classification: str  # "STATIC", "REPETITIVE", "DYNAMIC"

@dataclass
class CropRegion:
    """Crop coordinates for a single frame in 9:16 output."""
    cx: int  # center x in source frame
    cy: int  # center y in source frame
    w: int   # crop width in source
    h: int   # crop height in source

@dataclass
class ProcessedSegment:
    """A segment ready for rendering."""
    start: float
    end: float
    speed_factor: float  # 1.0 = normal, 3.5 = speed ramp
    is_beat_cut: bool    # True = hard cut at beat drop
    classification: str

@dataclass(frozen=True)
class TextEventUnbox:
    """A text overlay event."""
    start: float
    text: str
    event_type: str  # "hook" or "feature"
