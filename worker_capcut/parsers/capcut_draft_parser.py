import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class CapCutDraftParser:
    """
    Parser for CapCut project drafts.
    Extracts high-level semantic structures (timelines, pacing, text slots, effects)
    and removes local file paths, UUIDs, and system-specific metadata.
    Generates a clean text/JSON representation of the template structure for AI training and RAG ingestion.
    """
    
    def __init__(self, draft_path: str):
        self.draft_path = draft_path
        self.content_json_path = os.path.join(draft_path, "draft_content.json")
        self.meta_json_path = os.path.join(draft_path, "draft_meta_info.json")
        
    def parse(self) -> Dict[str, Any]:
        """
        Parses draft_content.json and draft_meta_info.json.
        Returns a simplified Semantic Video Graph.
        """
        if not os.path.exists(self.content_json_path):
            raise FileNotFoundError(f"draft_content.json not found at {self.content_json_path}")
            
        content_str = None
        # Try different encodings/methods to load content
        encodings = ['utf-8-sig', 'utf-16', 'utf-8']
        
        for enc in encodings:
            try:
                with open(self.content_json_path, 'r', encoding=enc) as f:
                    content_str = f.read().strip()
                if content_str:
                    break
            except Exception:
                continue
                
        if not content_str:
            try:
                with open(self.content_json_path, 'rb') as f:
                    content_bytes = f.read()
                content_str = content_bytes.decode('utf-8', errors='ignore').strip()
            except Exception as e:
                raise ValueError(f"Không thể đọc file draft_content.json: {e}")
                
        # Validate that the file is not encrypted/corrupt (must start with { or [)
        if not (content_str.startswith('{') or content_str.startswith('[')):
            raise ValueError(
                "Bản nháp CapCut này bị mã hóa hoặc không đúng định dạng JSON (thường do là template tải trực tiếp từ cửa hàng CapCut/剪映). "
                "Để hệ thống học được, vui lòng mở bản nháp này trong phần mềm CapCut trên máy tính, thực hiện Nhân bản (Duplicate) "
                "hoặc chỉnh sửa nhẹ rồi lưu thành một Dự án cục bộ (Local Project) thông thường, sau đó thử học lại Dự án cục bộ vừa tạo!"
            )
            
        try:
            content = json.loads(content_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Lỗi cấu trúc JSON trong draft_content.json: {e}")
            
        meta = {}
        if os.path.exists(self.meta_json_path):
            meta_str = None
            for enc in encodings:
                try:
                    with open(self.meta_json_path, 'r', encoding=enc) as f:
                        meta_str = f.read().strip()
                    if meta_str:
                        break
                except Exception:
                    continue
            
            if not meta_str:
                try:
                    with open(self.meta_json_path, 'rb') as f:
                        meta_bytes = f.read()
                    meta_str = meta_bytes.decode('utf-8', errors='ignore').strip()
                except Exception:
                    pass
            
            if meta_str and (meta_str.startswith('{') or meta_str.startswith('[')):
                try:
                    meta = json.loads(meta_str)
                except Exception as e:
                    logger.warning(f"Failed to parse draft_meta_info.json JSON: {e}")
                
        # 1. Extract global settings
        width = content.get("canvas_config", {}).get("width", 1080)
        height = content.get("canvas_config", {}).get("height", 1920)
        ratio = content.get("canvas_config", {}).get("ratio", "9:16")
        fps = content.get("fps", 30.0)
        duration_us = content.get("duration", 0)  # Microseconds
        duration_seconds = round(duration_us / 1000000.0, 2)
        
        # 2. Extract materials mapping to resolve filenames
        # We want to replace actual filenames with generic placeholders like [IMAGE_1], [AUDIO_1]
        materials = content.get("materials", {})
        video_materials = {v["id"]: v for v in materials.get("videos", [])}
        audio_materials = {a["id"]: a for a in materials.get("audios", [])}
        
        # Build maps for local asset replacements
        asset_map = {}
        image_counter = 1
        video_counter = 1
        audio_counter = 1
        
        # 3. Extract tracks
        tracks = content.get("tracks", [])
        parsed_tracks = []
        
        # Helper to get material name or assign a placeholder
        def get_asset_placeholder(material_id: str, metetype: str) -> str:
            if material_id in asset_map:
                return asset_map[material_id]
                
            nonlocal image_counter, video_counter, audio_counter
            if metetype == "photo" or material_id in video_materials and video_materials[material_id].get("type") == "photo":
                placeholder = f"[IMAGE_{image_counter}]"
                image_counter += 1
            elif metetype == "music" or material_id in audio_materials:
                placeholder = f"[AUDIO_{audio_counter}]"
                audio_counter += 1
            else:
                placeholder = f"[VIDEO_{video_counter}]"
                video_counter += 1
                
            asset_map[material_id] = placeholder
            return placeholder

        for track in tracks:
            track_type = track.get("type")
            track_name = track.get("name") or track_type
            segments = track.get("segments", [])
            
            parsed_segments = []
            for seg in segments:
                # Calculate relative timing in seconds
                target_range = seg.get("target_timerange", {})
                start_sec = round(target_range.get("start", 0) / 1000000.0, 2)
                duration_sec = round(target_range.get("duration", 0) / 1000000.0, 2)
                end_sec = round(start_sec + duration_sec, 2)
                
                material_id = seg.get("material_id")
                
                seg_info = {
                    "start": start_sec,
                    "duration": duration_sec,
                    "end": end_sec,
                }
                
                if track_type == "video":
                    # Determine if it's photo or video
                    metetype = "video"
                    if material_id in video_materials:
                        mat = video_materials[material_id]
                        if mat.get("type") == "photo" or "image" in mat.get("material_name", "").lower():
                            metetype = "photo"
                    
                    seg_info["placeholder"] = get_asset_placeholder(material_id, metetype)
                    
                    # Extract transitions
                    # Note: transition info is usually placed in transitions list or within extra refs,
                    # but since we clean it, we check if VectCutAPI-styled transition metadata or clip settings exist.
                    # In CapCut, transitions are separate materials or effects.
                    # We look for "transition" or effect references.
                    # For simplicity, we also inspect common properties.
                    # If this is a learned draft, we look at the segment settings:
                    if seg.get("transition"):
                        seg_info["transition"] = seg.get("transition")
                    if seg.get("intro_animation"):
                        seg_info["intro_animation"] = seg.get("intro_animation")
                        seg_info["intro_animation_duration"] = seg.get("intro_animation_duration", 0.5)
                    if seg.get("outro_animation"):
                        seg_info["outro_animation"] = seg.get("outro_animation")
                        seg_info["outro_animation_duration"] = seg.get("outro_animation_duration", 0.5)
                        
                elif track_type == "text":
                    # Texts are stored in materials under texts
                    text_materials = {t["id"]: t for t in materials.get("texts", [])}
                    text_content = ""
                    if material_id in text_materials:
                        # Strip html tags if CapCut uses styled text
                        raw_text = text_materials[material_id].get("content", "")
                        # Simple rich text tags stripping (e.g. <size=...>Text</size>)
                        import re
                        text_content = re.sub(r'<[^>]+>', '', raw_text)
                    
                    seg_info["text_content"] = text_content
                    
                elif track_type == "audio":
                    seg_info["placeholder"] = get_asset_placeholder(material_id, "music")
                    
                # Look for visual effects applied to this segment time-range
                # CapCut effects usually reside on their own track, or inside extra_material_refs
                parsed_segments.append(seg_info)
                
            if parsed_segments:
                parsed_tracks.append({
                    "track_name": track_name,
                    "track_type": track_type,
                    "segments": sorted(parsed_segments, key=lambda x: x["start"])
                })
                
        # 4. Generate structured summary
        summary = {
            "template_name": meta.get("draft_name", os.path.basename(self.draft_path)),
            "resolution": f"{width}x{height}",
            "aspect_ratio": ratio,
            "duration_seconds": duration_seconds,
            "fps": fps,
            "tracks": parsed_tracks
        }
        
        return summary
        
    def generate_markdown_summary(self, summary: Dict[str, Any]) -> str:
        """
        Formats the Semantic Video Graph JSON into a rich, structured Markdown text.
        This markdown is ideal for LLM ingestion and RAG search.
        """
        md = []
        md.append(f"# CapCut Template Blueprint: {summary['template_name']}")
        md.append("")
        md.append("## Global Configurations")
        md.append(f"- **Resolution**: {summary['resolution']}")
        md.append(f"- **Aspect Ratio**: {summary['aspect_ratio']}")
        md.append(f"- **Duration**: {summary['duration_seconds']}s")
        md.append(f"- **FPS**: {summary['fps']}")
        md.append("")
        md.append("## Timeline Track Structure")
        md.append("")
        
        for track in summary["tracks"]:
            md.append(f"### Track: {track['track_name']} (Type: {track['track_type']})")
            md.append("| Segment # | Start (s) | End (s) | Duration (s) | Content / Transition / FX |")
            md.append("| :--- | :--- | :--- | :--- | :--- |")
            
            for idx, seg in enumerate(track["segments"]):
                details = []
                if "placeholder" in seg:
                    details.append(f"Source: `{seg['placeholder']}`")
                if "text_content" in seg:
                    details.append(f"Text Overlay: **\"{seg['text_content']}\"**")
                if "transition" in seg:
                    details.append(f"Transition: `{seg['transition']}`")
                if "intro_animation" in seg:
                    details.append(f"Intro Anim: `{seg['intro_animation']}` ({seg.get('intro_animation_duration', 0.5)}s)")
                if "outro_animation" in seg:
                    details.append(f"Outro Anim: `{seg['outro_animation']}` ({seg.get('outro_animation_duration', 0.5)}s)")
                    
                details_str = ", ".join(details) if details else "None"
                md.append(f"| {idx+1} | {seg['start']}s | {seg['end']}s | {seg['duration']}s | {details_str} |")
            md.append("")
            
        md.append("## Narrative Flow Analysis Prompt Hint")
        md.append("Analyzing the timing and text slots above, this template represents a structured story flow:")
        
        # Inferred pacing based on segment counts
        video_tracks = [t for t in summary["tracks"] if t["track_type"] == "video"]
        if video_tracks:
            segment_durations = [s["duration"] for s in video_tracks[0]["segments"]]
            avg_duration = sum(segment_durations) / len(segment_durations) if segment_durations else 0
            if avg_duration < 2.0:
                md.append("- **Pacing**: Ultra Fast-paced (dynamic TikTok style, viral trend, fast beats).")
            elif avg_duration < 4.0:
                md.append("- **Pacing**: Moderate / Engaging (product showcase, highlights, lifestyle vlog).")
            else:
                md.append("- **Pacing**: Slow / Informational (talking head, explanatory slides, educational).")
                
        return "\n".join(md)
