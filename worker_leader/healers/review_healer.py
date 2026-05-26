"""
Defensive healer for the ``review`` worker type.

Ensures ``assets``, ``timeline_script``, and per-segment fields are present
with sensible defaults when the LLM output is incomplete.
"""

from typing import Dict, Any, List


def heal_review(draft_params: Dict[str, Any], sentences: List[str]) -> Dict[str, Any]:
    """Logic sửa lỗi phòng thủ cho worker review."""
    if "assets" not in draft_params or not isinstance(draft_params["assets"], dict):
        draft_params["assets"] = {}
    assets = draft_params["assets"]

    if "audio" not in assets or not isinstance(assets["audio"], dict):
        assets["audio"] = {}
    if "bgm_path" not in assets["audio"] or not assets["audio"]["bgm_path"]:
        assets["audio"]["bgm_path"] = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"

    if "video_folders" not in assets or not isinstance(assets["video_folders"], dict):
        assets["video_folders"] = {
            "1": "https://assets.mixkit.co/videos/preview/mixkit-holding-a-smartphone-with-a-green-screen-41775-large.mp4"
        }

    review_points: List[str] = []
    if "review_points" in draft_params and isinstance(draft_params["review_points"], list):
        review_points = draft_params["review_points"]
    elif "points" in draft_params and isinstance(draft_params["points"], list):
        review_points = draft_params["points"]

    if ("timeline_script" not in draft_params or not isinstance(draft_params["timeline_script"], list)) and review_points:
        timeline_script = []
        for idx, pt in enumerate(review_points):
            timeline_script.append({
                "segment": f"0{idx+1}_point" if idx < 9 else f"{idx+1}_point",
                "video_source": "1",
                "time_range": [idx * 5, (idx + 1) * 5],
                "text_overlay": pt,
                "highlight_words": pt.split()[:2] if len(pt.split()) >= 2 else [pt],
                "visual_effects": ["camera_shake"] if idx == 0 else [],
                "pacing": {
                    "min_clip_duration": 0.8,
                    "max_clip_duration": 1.5,
                },
            })
        draft_params["timeline_script"] = timeline_script

    if "timeline_script" not in draft_params or not isinstance(draft_params["timeline_script"], list) or len(draft_params["timeline_script"]) == 0:
        timeline_script = []
        for idx, sen in enumerate(sentences[:5]):
            segment_name = (
                "01_hook"
                if idx == 0
                else (
                    f"0{idx+1}_body"
                    if idx < len(sentences[:5]) - 1
                    else f"0{idx+1}_outro"
                )
            )
            timeline_script.append({
                "segment": segment_name,
                "video_source": "1",
                "time_range": [idx * 6, (idx + 1) * 6],
                "text_overlay": sen,
                "highlight_words": sen.split()[:2] if len(sen.split()) >= 2 else [sen],
                "visual_effects": ["camera_shake"] if idx == 0 else [],
                "pacing": {
                    "min_clip_duration": 0.8,
                    "max_clip_duration": 1.5,
                },
            })
        draft_params["timeline_script"] = timeline_script

    for idx, seg in enumerate(draft_params["timeline_script"]):
        if not isinstance(seg, dict):
            continue
        if "segment" not in seg:
            seg["segment"] = f"segment_{idx+1}"
        if "video_source" not in seg:
            seg["video_source"] = "1"
        if "time_range" not in seg:
            seg["time_range"] = [idx * 5, (idx + 1) * 5]
        if "text_overlay" not in seg:
            seg["text_overlay"] = sentences[idx % len(sentences)]
        if "highlight_words" not in seg:
            words = seg["text_overlay"].split()
            seg["highlight_words"] = words[:2] if len(words) >= 2 else words
        if "visual_effects" not in seg:
            seg["visual_effects"] = []
        if "pacing" not in seg:
            seg["pacing"] = {"min_clip_duration": 0.8, "max_clip_duration": 1.5}

    draft_params.pop("review_points", None)
    draft_params.pop("points", None)
    return draft_params
