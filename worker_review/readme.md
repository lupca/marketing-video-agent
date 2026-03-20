echo "1. Cài đặt các thư viện Python..."
pip install -r requirements.txt

echo "2. Cài đặt FFmpeg xịn..."
brew install ffmpeg

echo "3. Tải trước Model Tiếng Việt (Warm-up)..."
source /Users/dangtung/projects/video-creater/video-review/.venv/bin/activate && python -c "
from huggingface_hub import snapshot_download
print('Downloading wav2vec2-base-vietnamese-250h...', flush=True)
path = snapshot_download('nguyenvulebinh/wav2vec2-base-vietnamese-250h')
print('Downloaded to:', path, flush=True)
"

echo "XONG! HỆ THỐNG ĐÃ SẴN SÀNG CHẠY AUTO MƯỢT MÀ."

source /Users/dangtung/projects/video-creater/video-review/.venv/bin/activate && cd /Users/dangtung/projects/video-creater/video-review && python video_builder.py
