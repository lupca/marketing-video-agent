# Hướng Dẫn Sử Dụng - Video Marketing Pipeline

## 1) Yêu cầu hệ thống
- macOS/Linux có cài `ffmpeg` và `ffprobe`
- Python 3.9+
- Dependency trong [requirements.txt](../requirements.txt)

## 2) Chuẩn bị dữ liệu
Đặt file trong thư mục [input](../input):
- Nhiều clip `.mov` (video raw)
- 1 file MP3 nhạc nền, mặc định đang là:
  - `the_mountain-tiktok-453510.mp3`

## 3) Cài đặt
Từ root project:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4) Cấu hình nhanh
Mở [make_viral.py](../make_viral.py), cập nhật các biến:
- `INPUT_DIR`, `OUTPUT_DIR`
- `RAW_CLIPS` (glob `*.mov`)
- `TIKTOK_MP3`
- `TEXT_EVENTS`

Ví dụ `TEXT_EVENTS`:

```python
TEXT_EVENTS = [
    {"time": 0.0, "text": "VỢT CẦU LÔNG SIÊU ĐỈNH", "effect": "hook"},
    {"time": 3.2, "text": "Cuốn cán chính hãng", "effect": "feature"},
]
```

## 5) Chạy pipeline

```bash
python3 make_viral.py
```

Output mặc định:
- [output/viral_final.mp4](../output/viral_final.mp4)

## 6) Kiểm tra output

```bash
ffprobe -v error \
  -show_entries stream=codec_name,width,height,r_frame_rate,codec_type:format=duration,size \
  -of default=noprint_wrappers=1 \
  output/viral_final.mp4
```

Mục tiêu thông thường:
- Video: 1080x1920, 30fps, h264
- Audio: aac

## 7) Tinh chỉnh theo nhu cầu

### Chuyển cảnh chậm hơn / nhanh hơn
- Sửa `xfade_duration` trong hàm `_concat_scenes()`:
  - Tăng lên (0.6-0.8): mềm hơn, chậm hơn
  - Giảm xuống (0.2-0.4): nhanh hơn

### Nhịp cắt cảnh
- Sửa:
  - `scene_min_seconds`
  - `scene_max_seconds`

### Độ nét / dung lượng
- Sửa:
  - `crf` (thấp hơn -> nét hơn, file lớn hơn)
  - `preset` (chậm hơn -> nén tốt hơn)

### Tốc độ zoom Ken Burns
- Sửa trong `_render_scene()`:
  - `z='min(zoom+0.0015,1.15)'`
- Ví dụ:
  - `0.0012`: zoom êm hơn
  - `0.0018`: zoom rõ hơn

## 8) Lỗi thường gặp và cách xử lý

### Lỗi: ffmpeg/ffprobe not found
- Cài ffmpeg và đảm bảo command có trong PATH.

### Lỗi overlay drawtext
- Máy không hỗ trợ drawtext sẽ fallback MoviePy/Pillow.
- Nếu vẫn lỗi, kiểm tra font trong `_resolve_font()`.

### Video bị giật/rung khi zoom
- Xác nhận zoompan có:
  - `s=1080x1920`
  - `fps=30`

### Output quá ngắn/quá dài
- Quá ngắn:
  - Tăng `scene_max_seconds`
  - Giảm `xfade_duration`
- Quá dài:
  - Giảm `scene_max_seconds`
  - Tăng tốc độ zoom/nhiều cắt cảnh hơn

## 9) Lệnh debug nhanh

```bash
python3 -m py_compile make_viral.py
python3 make_viral.py
```

Nếu cần giữ file tạm để debug:
- Đặt `keep_temp=True` khi tạo `VideoViralEngine(...)`

## 10) Quy trình để team bảo trì dễ
1. Sửa config và text events
2. Chạy local và verify ffprobe
3. Review nội dung scene + transition
4. Chốt preset/crf
5. Commit kèm note tham số đã dùng (fps, crf, preset, xfade_duration)
