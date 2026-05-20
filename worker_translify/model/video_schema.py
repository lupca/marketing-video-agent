from typing import List, Optional
from pydantic import BaseModel, Field

class SpeakerData(BaseModel):
    id: str = Field(default="A", description="Identifier for the speaker in this scene")
    face_bbox: List[List[float]] = Field(default_factory=list, description="Bounding box for speaker's face [[x1,y1], [x2,y2], ...]")
    emotion_src: str = Field(default="neutral", description="Detected emotion of the speaker in the source scene")

class AudioData(BaseModel):
    zh_text: str = Field(..., description="Original Chinese transcript for the scene")
    vi_text: Optional[str] = Field(default=None, description="Translated Vietnamese transcript")
    duration: float = Field(..., description="Duration of the audio segment in seconds")
    tts_file: Optional[str] = Field(default=None, description="Path to synthesized Vietnamese TTS audio file")
    emotion_target: Optional[str] = Field(default=None, description="Target emotion style for TTS generation")

class OcrItem(BaseModel):
    bbox: List[List[float]] = Field(..., description="Bounding box points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]")
    text_zh: str = Field(..., description="Detected text in Chinese")
    text_vi: Optional[str] = Field(default=None, description="Translated text in Vietnamese")
    time_sec: float = Field(default=0.0, description="Timestamp of the frame where this OCR item was detected")

class VisualData(BaseModel):
    ocr_text: List[OcrItem] = Field(default_factory=list, description="List of on-screen OCR text items detected in the scene")

class BgmData(BaseModel):
    type: str = Field(default="original", description="Type of BGM (original, custom, etc.)")
    volume: float = Field(default=0.5, description="Volume level for the background music")

class Scene(BaseModel):
    id: str = Field(..., description="Unique scene ID")
    start: float = Field(..., description="Start timestamp of the scene relative to full video")
    end: float = Field(..., description="End timestamp of the scene relative to full video")
    speaker: SpeakerData = Field(default_factory=SpeakerData)
    audio: AudioData
    visual: VisualData = Field(default_factory=VisualData)
    bgm: BgmData = Field(default_factory=BgmData)

class VideoProject(BaseModel):
    video_id: str = Field(..., description="Unique project / video ID")
    scenes: List[Scene] = Field(default_factory=list, description="List of scenes in this video project")
