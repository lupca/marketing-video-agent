import os

path = "/root/marketing-video-agent/worker_translify/venv/lib/python3.10/site-packages/paddleocr/_pipelines/ocr.py"
if os.path.exists(path):
    with open(path, "r") as f:
        lines = f.readlines()
    for i, line in enumerate(lines[199:268]):
        print(f"{i+200}: {line}", end="")
else:
    print("File not found")
