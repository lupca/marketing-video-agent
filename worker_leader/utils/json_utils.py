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


def extract_json_from_text(text: str) -> dict:
    """
    Tìm và parse JSON từ văn bản kết quả của LLM/Agent.
    Hỗ trợ bóc tách JSON kể cả khi bị lẫn lộn giữa các đoạn text luyên thuyên.
    Chiến thuật: Tìm cặp ngoặc nhọn { } lớn nhất bao phủ toàn bộ khối dữ liệu.
    """
    json_str = ""
    text = text.strip()

    # Strategy 1: Direct parse attempt (cleanest case)
    try:
        return json.loads(text)
    except Exception:
        pass

    # Strategy 2: Fenced code block (```json ... ```)
    # Dùng lazy match .*? để tránh nuốt nhầm các block khác nếu có
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        json_str = match.group(1).strip()
    
    # Strategy 3: Outermost braces (Best for conversational LLMs like 3.5 9B)
    if not json_str:
        # Tìm vị trí { đầu tiên và } cuối cùng trong toàn bộ văn bản
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1].strip()

    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Tự động sửa các lỗi cú pháp cơ bản (trailing commas, unquoted Hook, v.v.)
            fixed_str = _auto_fix_json(json_str)
            try:
                return json.loads(fixed_str)
            except Exception:
                # Nỗ lực cuối cùng: Tự cân bằng ngoặc (LIFO order fix)
                # Đếm và đóng ngoặc theo thứ tự ngược lại để đảm bảo đúng cú pháp ]}
                open_braces = fixed_str.count('{')
                close_braces = fixed_str.count('}')
                open_brackets = fixed_str.count('[')
                close_brackets = fixed_str.count(']')
                
                temp_fixed = fixed_str
                # Nếu thiếu ngoặc vuông trong mảng, đóng nó trước
                if open_brackets > close_brackets:
                    temp_fixed += ']' * (open_brackets - close_brackets)
                # Sau đó mới đóng ngoặc nhọn của object
                if open_braces > close_braces:
                    temp_fixed += '}' * (open_braces - close_braces)
                
                try:
                    return json.loads(temp_fixed)
                except Exception as final_ex:
                    raise ValueError(f"JSON Decode Error after extensive healing: {str(final_ex)}")

    raise ValueError(f"Không tìm thấy bất kỳ khối {{...}} nào trong văn bản trả về của AI.")


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
