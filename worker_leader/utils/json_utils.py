"""
JSON extraction utilities for parsing LLM/Agent output.
"""

import json
import re
from typing import Dict, Any, List


def _auto_fix_json(dirty_json_str: str) -> str:
    """
    Attempts to fix common LLM JSON syntax errors.
    """
    # 1. Fix trailing commas in arrays and objects: [1, 2, ] -> [1, 2]
    cleaned = re.sub(r',\s*([\]}])', r'\1', dirty_json_str)

    # 2. Fix a specific common error: "key": Hook: "value" -> "key": "Hook: value"
    # This specifically target the error reported by the user
    cleaned = re.sub(r'":\s*Hook:\s*"', r'": "Hook: ', cleaned)
    
    # 3. Handle unquoted key-value-like patterns if they are simple words (risky, keep it simple)
    # For now, let's stick to the most common ones.

    return cleaned


def extract_all_json_objects(text: str) -> List[str]:
    """Tìm tất cả các khối {...} có ngoặc cân bằng trong chuỗi."""
    results = []
    start_indices = [i for i, char in enumerate(text) if char == '{']
    
    for start_idx in start_indices:
        stack = 0
        in_string = False
        escape = False
        for i in range(start_idx, len(text)):
            char = text[i]
            if not escape and char == '"':
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    stack += 1
                elif char == '}':
                    stack -= 1
                    if stack == 0:
                        results.append(text[start_idx:i+1])
                        break
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
    return results


def extract_json_from_text(text: str) -> dict:
    """
    Tìm và parse JSON từ văn bản kết quả của LLM/Agent.
    Hỗ trợ bóc tách JSON kể cả khi bị lẫn lộn giữa các đoạn text luyên thuyên hoặc code Python (như def ...).
    """
    json_str = ""
    text = text.strip()

    # Strategy 1: Direct parse attempt (cleanest case)
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strategy 2: Fenced code block (```json ... ```)
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except Exception:
            pass # Fallthrough to healing or other strategies
    
    # Strategy 3: Find all balanced {...} blocks (Best for code-generating LLMs like 3.5 9B)
    blocks = extract_all_json_objects(text)
    valid_dicts = []
    
    for block in blocks:
        try:
            parsed = json.loads(block)
            if isinstance(parsed, dict):
                valid_dicts.append(parsed)
        except json.JSONDecodeError:
            # Try healing this block
            fixed_str = _auto_fix_json(block)
            try:
                parsed = json.loads(fixed_str)
                if isinstance(parsed, dict):
                    valid_dicts.append(parsed)
            except Exception:
                pass

    if valid_dicts:
        # Return the largest valid dictionary found (most likely the main config, not a nested snippet)
        return max(valid_dicts, key=lambda d: len(json.dumps(d)))

    # Strategy 4: Fallback to Outermost braces with extensive healing
    if not json_str:
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1].strip()

    if json_str:
        fixed_str = _auto_fix_json(json_str)
        # Nỗ lực cuối cùng: Tự cân bằng ngoặc (LIFO order fix)
        open_braces = fixed_str.count('{')
        close_braces = fixed_str.count('}')
        open_brackets = fixed_str.count('[')
        close_brackets = fixed_str.count(']')
        
        temp_fixed = fixed_str
        if open_brackets > close_brackets:
            temp_fixed += ']' * (open_brackets - close_brackets)
        if open_braces > close_braces:
            temp_fixed += '}' * (open_braces - close_braces)
        
        try:
            return json.loads(temp_fixed)
        except Exception as final_ex:
            raise ValueError(f"JSON Decode Error after extensive healing: {str(final_ex)}")

    raise ValueError(f"Không tìm thấy bất kỳ khối {{...}} hợp lệ nào trong văn bản trả về của AI.")


def extract_sentences_from_script(script_content: str, title: str) -> List[str]:
    """
    Extract meaningful sentences from script content for draft backups.

    Splits by newlines and periods, filters out short fragments (<=5 chars).
    Falls back to generic Vietnamese marketing sentences if nothing is extracted.

    Args:
        script_content: Raw script text.
        title: Video title used as fallback.

    Returns:
        List of meaningful sentence strings.
    """
    sentences: List[str] = []
    if script_content:
        # Tách câu đơn giản bằng dấu chấm, chấm hỏi, chấm than hoặc xuống dòng
        raw_parts = []
        for line in script_content.split("\n"):
            for part in line.split("."):
                part = part.strip()
                if part:
                    raw_parts.append(part)
        sentences = [s for s in raw_parts if len(s) > 5]  # chỉ lấy câu có nghĩa

    if not sentences:
        sentences = [
            title or "Giới thiệu sản phẩm ấn tượng",
            "Khám phá tính năng nổi bật vượt trội",
            "Mua ngay hôm nay để nhận ưu đãi!",
        ]
    return sentences
