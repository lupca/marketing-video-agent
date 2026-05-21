import json
with open("translify_tmp/project_db.json", "r", encoding="utf-8") as f:
    db = json.load(f)

print("Total scenes:", len(db["scenes"]))
print("Scenes list:")
for s in db["scenes"]:
    has_ocr = s["visual"]["ocr_text"]
    print(f"- {s['id']}: start={s['start']}s, end={s['end']}s, ocr={has_ocr}")
