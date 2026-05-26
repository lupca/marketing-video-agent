"""
Defensive healer for the ``translify`` worker type.

Ensures ``video`` URL and ``voice_name`` are present with sensible defaults.
"""

from typing import Dict, Any


def heal_translify(draft_params: Dict[str, Any]) -> Dict[str, Any]:
    """Logic sửa lỗi phòng thủ cho worker translify."""
    if "video" not in draft_params or not draft_params["video"]:
        draft_params["video"] = "https://assets.mixkit.co/videos/preview/mixkit-holding-a-smartphone-with-a-green-screen-41775-large.mp4"
    if "voice_name" not in draft_params or not draft_params["voice_name"]:
        draft_params["voice_name"] = "vi-VN-NamMinhNeural"
    return draft_params
