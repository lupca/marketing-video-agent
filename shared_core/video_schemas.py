"""
Standard Pydantic models and defensive healers for the Pure Scene-Centric Video Timeline.
Provides complete backward compatibility and robust text parsing.
"""

import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# ── 1. Robust Sentence Extractor with Metadata Filtering ───────────────────────

def extract_clean_sentences(script_content: str, title: str) -> List[str]:
    """
    Tách kịch bản thô thành các câu sạch và lọc bỏ hoàn toàn các dòng metadata/tiêu đề.
    """
    sentences: List[str] = []
    if script_content:
        raw_parts = []
        for line in script_content.split("\n"):
            for part in line.split("."):
                part = part.strip()
                if part:
                    raw_parts.append(part)
        
        for s in raw_parts:
            s_clean = s.strip()
            if len(s_clean) <= 5:
                continue
            
            # 1. Kết thúc bằng dấu hai chấm (e.g. "ADAPTED COPY:", "VIBE & MUSIC:")
            if s_clean.endswith(":"):
                continue
            
            # 2. Định dạng nhãn in hoa ngắn (e.g. "ADAPTED COPY", "INTRO", "HOOK")
            letters_only = re.sub(r'[^a-zA-Z\d\s]', '', s_clean)
            if letters_only.isupper() and len(s_clean) < 30:
                continue
            
            # 3. Bao bọc bởi ngoặc vuông/tròn (e.g. "[Hook 3s]", "(Scene 1)")
            if (s_clean.startswith("[") and s_clean.endswith("]")) or (s_clean.startswith("(") and s_clean.endswith(")")):
                continue
                
            # 4. Chứa các từ khóa tiêu đề phổ biến ở dạng ngắn hoặc đi kèm dấu hai chấm
            lower_s = s_clean.lower()
            if any(h in lower_s for h in ["adapted copy", "vibe & music", "vibe and music", "scene ", "clip ", "segment ", "outro", "intro"]):
                if len(s_clean) < 25 or ":" in s_clean:
                    continue
                    
            sentences.append(s_clean)

    if not sentences:
        sentences = [
            title or "Giới thiệu sản phẩm ấn tượng",
            "Khám phá tính năng nổi bật vượt trội",
            "Mua ngay hôm nay để nhận ưu đãi!",
        ]
    return sentences


# ── 2. Unified Scene-Centric Schema ───────────────────────────────────────────

class Scene(BaseModel):
    scene_id: str = ""
    clip_url: str = ""
    text_overlay: str = ""
    narration: str = ""
    duration: float = 5.0
    pacing: Dict[str, float] = Field(default_factory=lambda: {"min_clip_duration": 0.8, "max_clip_duration": 1.5})
    effects: List[str] = Field(default_factory=list)
    highlight_words: List[str] = Field(default_factory=list)


class VideoComposition(BaseModel):
    suggested_duration: float = 15.0
    aspect_ratio: str = "9:16"
    bgm_path: str = ""
    voice_name: str = ""
    scenes: List[Scene] = Field(default_factory=list)


# ── 3. Defensive Healer for VideoComposition ─────────────────────────────────

def heal_video_composition(
    worker_type: str,
    raw_dict: dict,
    script_content: str,
    title: str
) -> dict:
    """
    Đảm bảo 100% dữ liệu luôn hợp lệ theo chuẩn VideoComposition.
    Áp dụng tương thích ngược (Backward Compatibility) và chữa lỗi phòng thủ.
    """
    if not isinstance(raw_dict, dict):
        raw_dict = {}

    sentences = extract_clean_sentences(script_content, title)

    # ── A. Tương thích ngược: Đọc và nâng cấp từ các schema cũ ──────────────────
    scenes_list = []
    
    # 1. Trường hợp đã là cấu trúc mới (chứa scenes)
    if "scenes" in raw_dict and isinstance(raw_dict["scenes"], list) and len(raw_dict["scenes"]) > 0:
        scenes_list = raw_dict["scenes"]
    
    # 2. Trường hợp là review (timeline_script)
    elif "timeline_script" in raw_dict and isinstance(raw_dict["timeline_script"], list):
        v_folders = raw_dict.get("assets", {}).get("video_folders", {}) if isinstance(raw_dict.get("assets"), dict) else {}
        for idx, seg in enumerate(raw_dict["timeline_script"]):
            if not isinstance(seg, dict):
                continue
            t_range = seg.get("time_range", [idx * 5, (idx + 1) * 5])
            scenes_list.append({
                "scene_id": seg.get("segment", f"segment_{idx+1}"),
                "clip_url": v_folders.get(seg.get("video_source", "1"), ""),
                "text_overlay": seg.get("text_overlay", ""),
                "narration": sentences[idx % len(sentences)],
                "duration": float(t_range[1]) - float(t_range[0]),
                "pacing": seg.get("pacing", {"min_clip_duration": 0.8, "max_clip_duration": 1.5}),
                "effects": seg.get("visual_effects", []),
                "highlight_words": seg.get("highlight_words", [])
            })
            
    # 3. Trường hợp là unbox_viral (text_events)
    elif "text_events" in raw_dict and isinstance(raw_dict["text_events"], list):
        clips = raw_dict.get("clips", [])
        bgm = raw_dict.get("audio", "")
        for idx, ev in enumerate(raw_dict["text_events"]):
            if not isinstance(ev, dict):
                continue
            scenes_list.append({
                "scene_id": f"scene_{idx+1}",
                "clip_url": clips[idx % len(clips)] if clips else "",
                "text_overlay": ev.get("text", ""),
                "narration": sentences[idx % len(sentences)],
                "duration": 4.0,
                "effects": ["camera_shake"] if ev.get("effect") == "hook" else []
            })
            
    # 4. Trường hợp là slideshow (products)
    elif "input_json" in raw_dict and isinstance(raw_dict["input_json"], dict) and "products" in raw_dict["input_json"]:
        products = raw_dict["input_json"]["products"]
        for idx, p in enumerate(products):
            if not isinstance(p, dict):
                continue
            scenes_list.append({
                "scene_id": f"product_{idx+1}",
                "clip_url": p.get("image", ""),
                "text_overlay": p.get("text", ""),
                "narration": p.get("text", ""),
                "duration": 5.0,
                "effects": []
            })

    # ── B. Fallback hoàn toàn nếu không trích xuất được phân cảnh nào ──────────
    if not scenes_list:
        for idx, sen in enumerate(sentences[:4]):
            scenes_list.append({
                "scene_id": f"0{idx+1}_hook" if idx == 0 else f"0{idx+1}_body",
                "clip_url": "https://assets.mixkit.co/videos/preview/mixkit-unpacking-a-gift-box-41584-large.mp4",
                "text_overlay": sen,
                "narration": sen,
                "duration": 5.0,
                "effects": ["camera_shake"] if idx == 0 else []
            })

    # ── C. Chuẩn hóa và chèn các giá trị mặc định phòng thủ cho từng phân cảnh ──
    final_scenes = []
    for idx, sc in enumerate(scenes_list):
        if not isinstance(sc, dict):
            continue
            
        s_id = sc.get("scene_id") or (f"0{idx+1}_hook" if idx == 0 else f"0{idx+1}_body")
        c_url = sc.get("clip_url") or "https://assets.mixkit.co/videos/preview/mixkit-unpacking-a-gift-box-41584-large.mp4"
        text = sc.get("text_overlay") or sentences[idx % len(sentences)]
        narr = sc.get("narration") or text
        dur = max(float(sc.get("duration", 5.0)), 1.0)
        
        # Pacing
        pacing = sc.get("pacing")
        if not isinstance(pacing, dict):
            pacing = {"min_clip_duration": 0.8, "max_clip_duration": 1.5}
            
        # Effects
        effects = sc.get("effects") or []
        if isinstance(effects, str):
            effects = [effects]
        if idx == 0 and "camera_shake" not in effects:
            effects.append("camera_shake")
            
        # Highlight words
        highlight = sc.get("highlight_words") or []
        if not highlight and text:
            words = text.split()
            highlight = words[:2] if len(words) >= 2 else [text]

        final_scenes.append({
            "scene_id": s_id,
            "clip_url": c_url,
            "text_overlay": text,
            "narration": narr,
            "duration": dur,
            "pacing": pacing,
            "effects": effects,
            "highlight_words": highlight
        })

    # ── D. Hoàn thiện đối tượng VideoComposition ─────────────────────────────────
    bgm = raw_dict.get("bgm_path") or raw_dict.get("audio")
    if not bgm or not isinstance(bgm, str):
        bgm = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"
        
    voice = raw_dict.get("voice_name") or "vi-VN-NamMinhNeural"
    dur_total = sum(s["duration"] for s in final_scenes)

    return {
        "suggested_duration": float(raw_dict.get("suggested_duration", dur_total)),
        "aspect_ratio": str(raw_dict.get("aspect_ratio", "9:16")),
        "bgm_path": bgm,
        "voice_name": voice,
        "scenes": final_scenes
    }
