"""
Video pacing validation tool for SmolAgents.

Checks words-per-second (WPS) across timeline segments and warns
when any segment exceeds the 4.5 WPS readability threshold.
"""

import json
from smolagents import tool


@tool
def validate_video_pacing(timeline_script_str: str) -> str:
    """
    Quét kịch bản timeline dạng JSON, đếm số từ trên giây (words per second) ở mỗi phân cảnh.
    Nếu có phân cảnh vượt quá 4.5 từ/giây, cảnh báo cho LLM và yêu cầu LLM chia đôi phân cảnh đó hoặc rút gọn văn bản.

    Args:
        timeline_script_str: Kịch bản timeline dưới dạng chuỗi JSON string cần kiểm tra.
    """
    try:
        data = json.loads(timeline_script_str)
        warnings = []
        segments = _extract_segments(data)

        if segments is None:
            return "Cấu trúc JSON không chứa timeline_script hoặc products/text_events để kiểm tra."

        for seg in segments:
            if not isinstance(seg, dict):
                continue
            warning = _check_segment_pacing(seg)
            if warning:
                warnings.append(warning)

        if warnings:
            return "\n".join(warnings)
        return "Tất cả các phân cảnh đều có nhịp độ (pacing) hợp lý, dưới 4.5 từ/giây."
    except Exception as e:
        return f"Lỗi khi kiểm tra pacing: {str(e)}"


# ── Internal Helpers ──────────────────────────────────────────────────────────


def _extract_segments(data) -> list | None:
    """
    Normalize different JSON structures into a flat list of segment dicts.

    Returns ``None`` if the structure is unrecognized.
    """
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return None

    if "timeline_script" in data:
        return data["timeline_script"]

    if "input_json" in data and "products" in data["input_json"]:
        segments = []
        for idx, p in enumerate(data["input_json"]["products"]):
            segments.append({
                "segment": p.get("hook", f"slide_{idx+1}"),
                "text_overlay": p.get("text", ""),
                "time_range": [0, 5],
            })
        return segments

    if "text_events" in data:
        events = data["text_events"]
        segments = []
        for i, ev in enumerate(events):
            nxt_time = events[i + 1]["time"] if i < len(events) - 1 else ev["time"] + 4.0
            duration = max(nxt_time - ev["time"], 1.0)
            segments.append({
                "segment": f"event_{i+1}",
                "text_overlay": ev.get("text", ""),
                "time_range": [ev["time"], ev["time"] + duration],
            })
        return segments

    return None


def _check_segment_pacing(seg: dict) -> str | None:
    """
    Check a single segment's words-per-second.

    Returns a warning string if WPS > 4.5, otherwise ``None``.
    """
    name = seg.get("segment") or seg.get("video_source") or "unnamed"
    text = seg.get("text_overlay") or seg.get("text") or ""
    time_range = seg.get("time_range")
    if not text or not time_range or len(time_range) < 2:
        return None

    duration = max(float(time_range[1]) - float(time_range[0]), 0.5)
    word_count = len(text.split())
    wps = word_count / duration

    if wps > 4.5:
        return (
            f"Phân cảnh '{name}' quá nhanh: {wps:.2f} từ/giây (vượt quá giới hạn 4.5 từ/giây). "
            f"Số từ: {word_count}, Thời lượng: {duration}s. "
            f"Hãy chia đôi cảnh này hoặc giảm bớt chữ trong text_overlay."
        )
    return None
