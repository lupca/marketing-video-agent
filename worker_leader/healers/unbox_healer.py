"""
Defensive healer for the ``unbox_viral`` worker type.

Ensures ``clips``, ``audio``, and ``text_events`` are present with
sensible defaults.
"""

from typing import Dict, Any, List


def heal_unbox_viral(draft_params: Dict[str, Any], sentences: List[str]) -> Dict[str, Any]:
    """Logic sửa lỗi phòng thủ cho worker unbox_viral."""
    if "clips" not in draft_params or not isinstance(draft_params["clips"], list) or len(draft_params["clips"]) == 0:
        draft_params["clips"] = ["https://assets.mixkit.co/videos/preview/mixkit-unpacking-a-gift-box-41584-large.mp4"]
    if "audio" not in draft_params or not draft_params["audio"]:
        draft_params["audio"] = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"

    if "text_events" not in draft_params or not isinstance(draft_params["text_events"], list) or len(draft_params["text_events"]) == 0:
        text_events = []
        for idx, sen in enumerate(sentences[:3]):
            text_events.append({
                "time": float(idx * 3.5),
                "text": sen,
                "effect": "hook" if idx == 0 else "feature",
            })
        draft_params["text_events"] = text_events

    for idx, ev in enumerate(draft_params["text_events"]):
        if not isinstance(ev, dict):
            continue
        if "time" not in ev:
            ev["time"] = float(idx * 3.0)
        if "text" not in ev:
            ev["text"] = sentences[idx % len(sentences)]
        if "effect" not in ev:
            ev["effect"] = "hook" if idx == 0 else "feature"
    return draft_params
