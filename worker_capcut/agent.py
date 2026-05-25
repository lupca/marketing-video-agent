"""
CapCut Skill Agent for parameter translation and plan healing.
"""

import json
import logging
import requests
from typing import List, Dict, Any
try:
    from skill import get_skill_markdown, sanitize_segment
except ImportError:
    from .skill import get_skill_markdown, sanitize_segment

logger = logging.getLogger(__name__)

class CapCutSkillAgent:
    """
    A specialized AI Agent equipped with CapCut video editing skills.
    Translates high-level abstract editing plans into precise, valid CapCut parameters.
    """

    def __init__(self):
        self.skill_context = get_skill_markdown()
        
    def _heuristic_translate(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deterministic heuristic translation fallback for common abstract patterns.
        Always executed first as a baseline, and used as fallback if LLM is unavailable.
        """
        direct_mappings = {
            "fade_in": {"transition": "Dissolve", "intro_animation": "Fade_In"},
            "fade_out": {"transition": "Dissolve", "outro_animation": "Fade_Out"},
            "fade": {"transition": "Dissolve"},
            "camera_shake": {"visual_effects": ["Shake_3"]},
        }
        
        healed = []
        for seg in timeline:
            new_seg = dict(seg)
            trans = new_seg.get("transition")
            if trans and trans.lower() in direct_mappings:
                maps = direct_mappings[trans.lower()]
                if "transition" in maps:
                    new_seg["transition"] = maps["transition"]
                if "intro_animation" in maps:
                    new_seg["intro_animation"] = maps["intro_animation"]
                    new_seg["intro_animation_duration"] = 0.5
                if "outro_animation" in maps:
                    new_seg["outro_animation"] = maps["outro_animation"]
                    new_seg["outro_animation_duration"] = 0.5
                    
            # Map abstract visual effects to known capcut effects
            effects = new_seg.get("visual_effects", [])
            new_effects = []
            for eff in effects:
                if eff.lower() in direct_mappings:
                    mapped_effs = direct_mappings[eff.lower()].get("visual_effects", [])
                    new_effects.extend(mapped_effs)
                else:
                    new_effects.append(eff)
            new_seg["visual_effects"] = new_effects
            
            # Post-sanitize to ensure exact matches
            healed.append(sanitize_segment(new_seg))
            
        return healed

    def translate_timeline(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Core agent workflow:
        1. Resolve LLM configuration (checking CapCut-specific settings & global settings).
        2. Build system prompt injecting CapCut Skills.
        3. Call LLM (Ollama/API) to perform smart translation.
        4. Parse & Validate output.
        5. Fallback to heuristic translation on failure.
        """
        logger.info(f"CapCutSkillAgent: Translating timeline of {len(timeline)} segments...")
        
        # 1. Prepare standard heuristic baseline
        baseline_timeline = self._heuristic_translate(timeline)
        
        try:
            from shared_core.config import get_settings
            settings = get_settings()
            
            base_url = settings.ollama.base_url
            model_name = settings.ollama.model_name
            api_key = ""
            
            # Resolve custom CapCut settings or global model configurations from Database
            try:
                from shared_core.database import SessionLocal as InternalSessionLocal
                from shared_core.models import SystemSetting
                with InternalSessionLocal() as db:
                    # 1. Check if there are CapCut-specific worker settings
                    capcut_setting = db.query(SystemSetting).filter(SystemSetting.key == "capcut_settings").first()
                    selected_model_id = "default"
                    
                    if capcut_setting and capcut_setting.value:
                        selected_model_id = capcut_setting.value.get("selected_model_id", "default")
                        
                    # If specific model ID is assigned, fetch it from llm_models list
                    if selected_model_id and selected_model_id != "default" and selected_model_id != "custom":
                        llm_models_setting = db.query(SystemSetting).filter(SystemSetting.key == "llm_models").first()
                        if llm_models_setting and llm_models_setting.value:
                            for m in llm_models_setting.value:
                                if m.get("id") == selected_model_id:
                                    base_url = m.get("base_url", base_url)
                                    model_name = m.get("model_name", model_name)
                                    api_key = m.get("api_key", "")
                                    logger.info(f"CapCutSkillAgent: Using assigned model config '{m.get('name')}'")
                                    break
                                    
                    # If customized manual overrides are set
                    elif selected_model_id == "custom" and capcut_setting.value:
                        base_url = capcut_setting.value.get("custom_base_url") or base_url
                        model_name = capcut_setting.value.get("custom_model_name") or model_name
                        api_key = capcut_setting.value.get("custom_api_key") or ""
                        logger.info("CapCutSkillAgent: Using custom manual parameter overrides")
                        
                    # Otherwise, fall back to global model_settings
                    else:
                        global_setting = db.query(SystemSetting).filter(SystemSetting.key == "model_settings").first()
                        if global_setting and global_setting.value:
                            base_url = global_setting.value.get("base_url") or base_url
                            model_name = global_setting.value.get("model_name") or model_name
                            api_key = global_setting.value.get("api_key") or ""
                            logger.info("CapCutSkillAgent: Inherited global model settings")
            except Exception as db_err:
                logger.warning(f"CapCutSkillAgent: DB settings fetch failed ({db_err}), using environment defaults.")

            system_prompt = (
                "You are the CapCut Video Editor Specialist Agent. Your job is to translate abstract video editing plans "
                "generated by the AI Leader Agent into precise, valid CapCut parameters supported by our VectCutAPI engine.\n\n"
                f"{self.skill_context}\n\n"
                "INSTRUCTIONS:\n"
                "1. Analyze the abstract timeline script below.\n"
                "2. Map abstract transition names (e.g. 'fade_in') to valid transition names (e.g. 'Dissolve') and intro/outro animations.\n"
                "3. Ensure all transition, intro_animation, and outro_animation properties strictly match case-sensitive names from the documentation.\n"
                "4. Return a valid JSON array of corrected segments. Ensure each segment contains the mapped properties if applicable:\n"
                "   - 'transition' (must be a valid transition name, or null/absent)\n"
                "   - 'intro_animation' (must be a valid CapCut_Intro_type, or null/absent)\n"
                "   - 'intro_animation_duration' (float, default 0.5)\n"
                "   - 'outro_animation' (must be a valid CapCut_Outro_type, or null/absent)\n"
                "   - 'outro_animation_duration' (float, default 0.5)\n"
                "5. All other original keys ('segment', 'video_source', 'time_range', 'text_overlay', 'highlight_words', 'visual_effects') must be preserved intact.\n\n"
                "Do not include any explanation or markdown formatting outside the JSON block. Return ONLY the JSON array/object."
            )

            user_content = f"Abstract input timeline script to translate:\n{json.dumps(timeline, ensure_ascii=False)}"
            
            api_url = f"{base_url.rstrip('/')}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
                
            req_payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "response_format": {"type": "json_object"}
            }
            
            logger.info(f"CapCutSkillAgent: Calling LLM at {api_url} with model {model_name}...")
            res = requests.post(api_url, json=req_payload, headers=headers, timeout=25)
            res.raise_for_status()
            
            ai_content = res.json()["choices"][0]["message"]["content"]
            logger.info(f"CapCutSkillAgent: Received LLM response: {ai_content}")
            
            parsed = json.loads(ai_content)
            translated_list = None
            if isinstance(parsed, list):
                translated_list = parsed
            elif isinstance(parsed, dict):
                for k in ["timeline", "timeline_script", "segments", "data"]:
                    if k in parsed and isinstance(parsed[k], list):
                        translated_list = parsed[k]
                        break
                if not translated_list:
                    # Check if the dict has a list-like values list
                    lists = [v for v in parsed.values() if isinstance(v, list)]
                    if lists:
                        translated_list = lists[0]
            
            if translated_list and isinstance(translated_list, list):
                logger.info("CapCutSkillAgent: Successfully parsed translation list from LLM.")
                # Sanitize and validate every segment to guarantee correctness
                sanitized_timeline = []
                for seg in translated_list:
                    if isinstance(seg, dict):
                        sanitized_timeline.append(sanitize_segment(seg))
                return sanitized_timeline

            logger.warning("CapCutSkillAgent: LLM returned invalid structure. Falling back to heuristic translation.")
        except Exception as e:
            logger.error(f"CapCutSkillAgent: LLM call failed ({e}). Falling back to heuristic translation.", exc_info=True)
            
        return baseline_timeline
