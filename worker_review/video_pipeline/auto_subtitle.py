from typing import Any, Dict, List
import logging


def generate_auto_subtitles(audio_path: str, logger: logging.Logger) -> List[Dict[str, Any]]:
    """
    Placeholder for future Whisper integration.

    Keep this function in a dedicated module so API/backend can swap
    implementation without touching the render pipeline.
    """
    logger.info(
        "auto_subtitle=true detected but Whisper is not integrated. "
        "See video_pipeline/auto_subtitle.py for integration point."
    )
    return []
