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

def extract_all_json_objects(text):
    results = []
    # Find all occurrences of '{'
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
                        json_str = text[start_idx:i+1]
                        results.append(json_str)
                        break # Found the matching closing brace for this start_idx
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
    return results

blocks = extract_all_json_objects(text)
for b in blocks:
    print("--- BLOCK ---")
    print(b)

def best_json(text):
    blocks = extract_all_json_objects(text)
    valid_dicts = []
    for b in blocks:
        try:
            parsed = json.loads(b)
            if isinstance(parsed, dict):
                valid_dicts.append(parsed)
        except:
            pass
    if valid_dicts:
        # Return the dictionary with the most keys, or string representation max length
        return max(valid_dicts, key=lambda d: len(str(d)))
    return None

print("Best:", best_json(text))
