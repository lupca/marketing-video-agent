"""
Standard parent-child video configuration schemas and Unified Auto-Mapping Engine.
Provides complete structural inheritance and 100% robust data mapping/recovery.
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


# ── 2. Standard Parent Schema (Base Configs) ──────────────────────────────────

class BaseTimelineSegment(BaseModel):
    """
    Cấu trúc cha chuẩn cho một phân đoạn video (scene/segment/product).
    """
    text: str = ""
    time: float = 0.0
    duration: float = 5.0
    effect: str = "feature"  # "hook" or "feature"
    image_or_video: str = ""
    hook_title: str = ""


class BaseVideoConfig(BaseModel):
    """
    Cấu trúc cha chuẩn chứa toàn bộ cấu hình lõi của video.
    """
    bgm_path: str = ""
    voice_name: str = ""
    clips: List[str] = Field(default_factory=list)
    segments: List[BaseTimelineSegment] = Field(default_factory=list)


# ── 3. Unified Auto-Mapping Engine ───────────────────────────────────────────

def find_sequence_list(draft_params: dict) -> list:
    """
    Quét đệ quy tìm kiếm bất kỳ danh sách chuỗi cảnh nào trong raw JSON từ LLM.
    """
    for key in ["timeline_script", "text_events", "products", "timeline", "segments", "scenes", "events", "items"]:
        val = draft_params.get(key)
        if isinstance(val, list) and len(val) > 0:
            return val
            
    input_json = draft_params.get("input_json")
    if isinstance(input_json, dict):
        for key in ["products", "timeline_script", "text_events", "timeline", "segments", "items"]:
            val = input_json.get(key)
            if isinstance(val, list) and len(val) > 0:
                return val
                
    # Quét đệ quy sâu hơn 1 cấp
    for k, val in draft_params.items():
        if isinstance(val, list) and len(val) > 0:
            if isinstance(val[0], dict) and any(tk in val[0] for tk in ["text", "text_overlay", "desc", "segment"]):
                return val
            elif isinstance(val[0], str):
                return val
        if isinstance(val, dict):
            for sub_k, sub_val in val.items():
                if isinstance(sub_val, list) and len(sub_val) > 0:
                    if isinstance(sub_val[0], dict) and any(tk in sub_val[0] for tk in ["text", "text_overlay", "desc", "segment"]):
                        return sub_val
                    elif isinstance(sub_val[0], str):
                        return sub_val
    return []


def parse_to_base_config(raw_dict: dict, sentences: list) -> BaseVideoConfig:
    """
    Ánh xạ bất kỳ cấu hình thô nào của LLM về cấu trúc cha chuẩn (BaseVideoConfig).
    """
    base_config = BaseVideoConfig()

    # 1. Trích xuất âm thanh (bgm)
    bgm = ""
    if "audio" in raw_dict:
        aud = raw_dict["audio"]
        if isinstance(aud, dict):
            bgm = aud.get("bgm_path", aud.get("bgm", ""))
        else:
            bgm = str(aud)
    elif "assets" in raw_dict and isinstance(raw_dict["assets"], dict):
        aud = raw_dict["assets"].get("audio")
        if isinstance(aud, dict):
            bgm = aud.get("bgm_path", aud.get("bgm", ""))
    base_config.bgm_path = bgm or "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"

    # 2. Trích xuất giọng đọc
    base_config.voice_name = raw_dict.get("voice_name", "vi-VN-NamMinhNeural")

    # 3. Trích xuất danh sách clips/video
    clips_list = []
    if "clips" in raw_dict and isinstance(raw_dict["clips"], list):
        clips_list = raw_dict["clips"]
    elif "assets" in raw_dict and isinstance(raw_dict["assets"], dict):
        v_folders = raw_dict["assets"].get("video_folders")
        if isinstance(v_folders, dict):
            clips_list = list(v_folders.values())
    elif "video" in raw_dict:
        clips_list = [raw_dict["video"]]
    
    # Loại bỏ giá trị trống
    clips_list = [c for c in clips_list if c]
    base_config.clips = clips_list or ["https://assets.mixkit.co/videos/preview/mixkit-unpacking-a-gift-box-41584-large.mp4"]

    # 4. Trích xuất và chuẩn hóa danh sách các phân đoạn
    raw_list = find_sequence_list(raw_dict)
    segments = []

    if raw_list:
        for idx, item in enumerate(raw_list):
            seg = BaseTimelineSegment()
            seg.time = float(idx * 3.5)
            seg.duration = 5.0
            seg.effect = "hook" if idx == 0 else "feature"

            if isinstance(item, str):
                seg.text = item
            elif isinstance(item, dict):
                # Lấy text hiển thị
                seg.text = (
                    item.get("text_overlay") or 
                    item.get("text") or 
                    item.get("desc") or 
                    item.get("description") or 
                    item.get("hook") or 
                    ""
                )
                # Lấy time / duration
                if "time_range" in item and isinstance(item["time_range"], list) and len(item["time_range"]) > 0:
                    try:
                        seg.time = float(item["time_range"][0])
                        if len(item["time_range"]) > 1:
                            seg.duration = max(1.0, float(item["time_range"][1]) - seg.time)
                    except (ValueError, TypeError):
                        pass
                elif "time" in item:
                    try:
                        seg.time = float(item["time"])
                    except (ValueError, TypeError):
                        pass
                # Lấy hiệu ứng
                eff = item.get("effect") or item.get("visual_effects")
                if isinstance(eff, list) and len(eff) > 0:
                    eff = eff[0]
                if eff:
                    eff_str = str(eff).lower()
                    if "hook" in eff_str or "camera_shake" in eff_str:
                        seg.effect = "hook"
                    else:
                        seg.effect = "feature"
                elif "segment" in item:
                    seg_str = str(item["segment"]).lower()
                    if "hook" in seg_str:
                        seg.effect = "hook"
                
                # Lấy image/video source
                seg.image_or_video = item.get("image") or item.get("video_source") or ""
                seg.hook_title = item.get("hook") or item.get("hook_title") or ""

            # Chỉ nạp nếu có text hữu ích hoặc fallback
            if not seg.text and sentences:
                seg.text = sentences[idx % len(sentences)]
            segments.append(seg)
    
    # Fallback hoàn toàn nếu không tìm thấy chuỗi nào
    if not segments:
        for idx, sen in enumerate(sentences[:4]):
            seg = BaseTimelineSegment(
                text=sen,
                time=float(idx * 3.5),
                duration=5.0,
                effect="hook" if idx == 0 else "feature"
            )
            segments.append(seg)

    base_config.segments = segments
    return base_config


# ── 4. Child Serializers to Specific Worker Schemas ───────────────────────────

def serialize_to_review(base_config: BaseVideoConfig, sentences: List[str]) -> dict:
    """
    Chuyển đổi cấu trúc cha chuẩn sang cấu hình chuẩn của Review Worker.
    """
    # 1. Map assets
    bgm = base_config.bgm_path or "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
    video_source_url = base_config.clips[0] if base_config.clips else "https://assets.mixkit.co/videos/preview/mixkit-holding-a-smartphone-with-a-green-screen-41775-large.mp4"
    
    assets = {
        "audio": {
            "bgm_path": bgm
        },
        "video_folders": {
            "1": video_source_url
        }
    }

    # 2. Map segments to timeline_script
    timeline_script = []
    for idx, seg in enumerate(base_config.segments):
        segment_name = "01_hook" if idx == 0 else (f"0{idx+1}_body" if idx < len(base_config.segments) - 1 else f"0{idx+1}_outro")
        words = seg.text.split()
        highlight = words[:2] if len(words) >= 2 else [seg.text]

        timeline_script.append({
            "segment": segment_name,
            "video_source": "1",
            "time_range": [seg.time, seg.time + seg.duration],
            "text_overlay": seg.text,
            "highlight_words": highlight,
            "visual_effects": ["camera_shake"] if seg.effect == "hook" else [],
            "pacing": {
                "min_clip_duration": 0.8,
                "max_clip_duration": 1.5
            }
        })

    return {
        "assets": assets,
        "timeline_script": timeline_script
    }


def serialize_to_unbox_viral(base_config: BaseVideoConfig) -> dict:
    """
    Chuyển đổi cấu trúc cha chuẩn sang cấu hình chuẩn của Unbox Viral Worker.
    """
    # 1. Map clips & audio
    clips = base_config.clips or ["https://assets.mixkit.co/videos/preview/mixkit-unpacking-a-gift-box-41584-large.mp4"]
    audio = base_config.bgm_path or "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"

    # 2. Map segments to text_events
    text_events = []
    for seg in base_config.segments:
        text_events.append({
            "time": seg.time,
            "text": seg.text,
            "effect": seg.effect
        })

    return {
        "clips": clips,
        "audio": audio,
        "text_events": text_events
    }


def serialize_to_slideshow(base_config: BaseVideoConfig, raw_dict: dict) -> dict:
    """
    Chuyển đổi cấu trúc cha chuẩn sang cấu hình chuẩn của Slideshow Worker.
    """
    # Trích xuất intro/outro
    input_json = raw_dict.get("input_json", {}) if isinstance(raw_dict.get("input_json"), dict) else {}
    intro = input_json.get("intro_text") or raw_dict.get("intro_text") or "Giới thiệu sản phẩm mới"
    outro = input_json.get("outro_text") or raw_dict.get("outro_text") or "Mua ngay tại giỏ hàng bên dưới!"

    # Map segments to products
    products = []
    for idx, seg in enumerate(base_config.segments):
        img_url = seg.image_or_video
        if not img_url or not str(img_url).startswith("http"):
            img_url = f"https://images.unsplash.com/photo-{1523275335684 + idx * 100}-37898b6baf30?w=500"

        products.append({
            "image": img_url,
            "text": seg.text,
            "hook": seg.hook_title or "Khám phá ngay"
        })

    return {
        "input_json": {
            "intro_text": intro,
            "outro_text": outro,
            "products": products
        }
    }


def serialize_to_translify(base_config: BaseVideoConfig) -> dict:
    """
    Chuyển đổi cấu trúc cha chuẩn sang cấu hình chuẩn của Translify Worker.
    """
    video_url = base_config.clips[0] if base_config.clips else "https://assets.mixkit.co/videos/preview/mixkit-holding-a-smartphone-with-a-green-screen-41775-large.mp4"
    voice = base_config.voice_name or "vi-VN-NamMinhNeural"
    return {
        "video": video_url,
        "voice_name": voice
    }


# ── 5. Unified Top-Level Entrypoint ───────────────────────────────────────────

def heal_and_map_config(
    worker_type: str,
    raw_dict: dict,
    script_content: str,
    title: str
) -> dict:
    """
    Top-level API cho toàn bộ hệ thống Healers.
    Đảm bảo map 100% dữ liệu từ bất kỳ cấu hình LLM thô nào sang cấu trúc của worker đích.
    """
    if not isinstance(raw_dict, dict):
        raw_dict = {}

    # Bước 1: Tách câu và lọc sạch metadata làm lớp dự phòng
    sentences = extract_clean_sentences(script_content, title)

    # Bước 2: Map cấu hình thô về cấu trúc cha chuẩn (Base Config)
    base_config = parse_to_base_config(raw_dict, sentences)

    # Bước 3: Serialize cấu trúc cha chuẩn về cấu hình của worker đích
    if worker_type == "review":
        return serialize_to_review(base_config, sentences)
    elif worker_type == "unbox_viral":
        return serialize_to_unbox_viral(base_config)
    elif worker_type == "slideshow":
        return serialize_to_slideshow(base_config, raw_dict)
    elif worker_type == "translify":
        return serialize_to_translify(base_config)

    return raw_dict
