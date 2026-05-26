import json

text = """
Thoughts: I need to create a proper video script following the marketing funnel structure, including video pacing validation. I'll use the correct code formatting for this task.

<code>
# Video Script Structure - Yonex Astrox 88 Play
video_script = {
    "title": "Đảm bảo chất lượng với Vợt Cầu Lông Yonex Astrox 88 Play Chính Hãng",
    "channel": "topvnsport",
    "duration_total": 15,
    "tone": "Gen-Z"
}
# Validate video pacing
def validate_video_pacing(script):
    return {
        "status": "PASS"
    }
</code>
"""

def extract_json(text):
    start_idx = text.find('{')
    if start_idx == -1:
        return None
    
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
                    json_str = text[start_idx:i+1]
                    return json_str
        if char == '\\' and not escape:
            escape = True
        else:
            escape = False
            
    return None

print(extract_json(text))
