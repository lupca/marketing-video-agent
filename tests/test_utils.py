import sys
sys.path.append('.')
from worker_leader.utils.json_utils import extract_json_from_text

text = """
Thoughts: I need to create a proper video script following the marketing funnel structure, including video pacing validation. I'll use the correct code formatting for this task.

<code>
# Video Script Structure - Yonex Astrox 88 Play
video_script = {
    "worker_type": "slideshow",
    "title": "Đảm bảo chất lượng với Vợt Cầu Lông Yonex Astrox 88 Play Chính Hãng"
}
# Validate video pacing
def validate_video_pacing(script):
    return {
        "status": "PASS"
    }
</code>
"""

print(extract_json_from_text(text))
