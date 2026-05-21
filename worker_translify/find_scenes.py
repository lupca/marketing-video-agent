import json
with open("translify_tmp/project_db.json", "r", encoding="utf-8") as f:
    data = json.load(f)
for s in data["scenes"]:
    dur = s["end"] - s["start"]
    print(f"{s['id']}: {s['start']:.2f}s - {s['end']:.2f}s (dur: {dur:.2f}s) - text: {len(s['visual']['ocr_text'])}")
