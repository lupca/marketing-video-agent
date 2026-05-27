from typing import TypedDict, List, Dict, Any, Optional
from model.video_schema import VideoProject

class TranslifyAgentState(TypedDict):
    job_id: int
    user_id: Optional[str]
    original_video_path: str
    project_data: VideoProject
    glossary: Optional[List[Dict[str, str]]]
    theme_summary: Optional[str]
    pacing_violations: List[str]
    trimming_attempts: Dict[str, int]
    config_data: Dict[str, Any]
