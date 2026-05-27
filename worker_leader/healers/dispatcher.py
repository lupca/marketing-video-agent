"""
Healer dispatcher — routes draft parameters to the correct worker-specific healer.
Now leverages the Pure Scene-Centric VideoComposition schema.
"""

from typing import Dict, Any
from shared_core.video_schemas import heal_video_composition

VALID_WORKER_TYPES = ["review", "slideshow", "unbox_viral", "translify"]


def heal_draft_parameters(
    worker_type: str,
    draft_params: Dict[str, Any],
    script_content: str,
    title: str,
) -> Dict[str, Any]:
    """
    Hậu xử lý và chuẩn hóa draft_parameters sử dụng cấu trúc phân cảnh đồng nhất.
    """
    return heal_video_composition(worker_type, draft_params, script_content, title)



