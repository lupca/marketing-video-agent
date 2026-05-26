"""
Healer dispatcher — routes draft parameters to the correct worker-specific healer.
"""

from typing import Dict, Any

from worker_leader.healers.review_healer import heal_review
from worker_leader.healers.slideshow_healer import heal_slideshow
from worker_leader.healers.unbox_healer import heal_unbox_viral
from worker_leader.healers.translify_healer import heal_translify
from worker_leader.utils.json_utils import extract_sentences_from_script


# Registry maps worker_type → healer function.
# Note: each healer has a different signature, dispatched explicitly below.
HEALERS_REGISTRY = {
    "review": heal_review,
    "slideshow": heal_slideshow,
    "unbox_viral": heal_unbox_viral,
    "translify": heal_translify,
}

VALID_WORKER_TYPES = list(HEALERS_REGISTRY.keys())


def heal_draft_parameters(
    worker_type: str,
    draft_params: Dict[str, Any],
    script_content: str,
    title: str,
) -> Dict[str, Any]:
    """
    Hậu xử lý và chuẩn hóa draft_parameters cho một worker cụ thể.

    Args:
        worker_type: The target worker type (e.g. ``"review"``, ``"slideshow"``).
        draft_params: Raw draft parameters dict from LLM output.
        script_content: The original script text.
        title: The video title.

    Returns:
        Healed draft_params dict with all required fields populated.
    """
    if not isinstance(draft_params, dict):
        draft_params = {}

    sentences = extract_sentences_from_script(script_content, title)

    healer = HEALERS_REGISTRY.get(worker_type)
    if healer:
        if worker_type == "slideshow":
            return healer(draft_params, sentences, title)
        elif worker_type in ("review", "unbox_viral"):
            return healer(draft_params, sentences)
        else:
            return healer(draft_params)

    return draft_params
