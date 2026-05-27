"""
Video pacing validation tool for SmolAgents.
Directly validates the unified Scene-Centric composition format.
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
        
        # Nâng cấp/đọc scenes
        scenes = data.get("scenes", [])
        if not scenes:
            return "Cấu trúc JSON không chứa timeline_script hoặc scenes để kiểm tra."

        for idx, sc in enumerate(scenes):
            if not isinstance(sc, dict):
                continue
                
            name = sc.get("scene_id") or f"scene_{idx+1}"
            text = sc.get("text_overlay") or sc.get("narration") or ""
            duration = max(float(sc.get("duration", 5.0)), 0.5)
            
            word_count = len(text.split())
            wps = word_count / duration
            
            if wps > 4.5:
                warnings.append(
                    f"Phân cảnh '{name}' quá nhanh: {wps:.2f} từ/giây (vượt quá giới hạn 4.5 từ/giây). "
                    f"Số từ: {word_count}, Thời lượng: {duration}s. "
                    f"Hãy chia đôi cảnh này hoặc giảm bớt chữ trong text_overlay."
                )

        if warnings:
            return "\n".join(warnings)
        return "Tất cả các phân cảnh đều có nhịp độ (pacing) hợp lý, dưới 4.5 từ/giây."
    except Exception as e:
        return f"Lỗi khi kiểm tra pacing: {str(e)}"

