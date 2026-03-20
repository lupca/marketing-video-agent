# Hướng dẫn sử dụng & cấu hình input/output cho AI

---

## 1. Project: video-review

### Input

- **input.json**: File cấu hình chính, gồm:
  - `metadata`: Thông tin dự án (project_id).
  - `assets`: Đường dẫn logo, audio, video raw.
    - `logo`: Vị trí, kích thước, độ mờ.
    - `audio`: voiceover_path, bgm_path, script, ngôn ngữ.
    - `video_folders`: mapping segment → thư mục video raw.
  - `timeline_script`: Mảng các segment, mỗi segment gồm:
    - `segment`: Tên phân đoạn (Hook, Reveal, Educate, Proof, CTA...).
    - `time_range`: [bắt đầu, kết thúc] (giây).
    - `video_source`: Tên thư mục video raw.
    - `text_overlay`: Text hiển thị lên video.
    - `highlight_words`: Từ cần làm nổi bật.
    - `visual_effects`: Hiệu ứng (camera_shake, snap_zoom, slow_motion...).
    - `pacing`: min/max duration cho từng clip.

- **raw/**: Thư mục chứa video raw, audio, voiceover.

### Output

- **output/{project_id}.mp4**: Video hoàn chỉnh.
- **output/{project_id}_captions.ass**: Subtitle (nếu có).
- Các file tạm, log, caption.

### Cách sử dụng

1. Chuẩn bị input.json đúng format.
2. Đặt video raw, audio vào đúng thư mục.
3. Chạy lệnh:
   ```
   python video_builder.py path/to/input.json
   ```
4. Kiểm tra output ở thư mục output/.

---

## 2. Project: video-unbox

### Input

- **input/**: Thư mục chứa:
  - Nhiều file `.mov` (video raw).
  - 1 file MP3 nhạc nền (the_mountain-tiktok-453510.mp3).
- **make_viral.py**: Cấu hình các biến:
  - `INPUT_DIR`, `OUTPUT_DIR`, `RAW_CLIPS`, `TIKTOK_MP3`.
  - `TEXT_EVENTS`: Lịch hiển thị text (dạng list dict).

### Output

- **output/viral_final.mp4**: Video hoàn chỉnh.
- Các file tạm, debug, log.

### Cách sử dụng

1. Cài đặt Python, ffmpeg, pip install -r requirements.txt.
2. Đặt video raw và nhạc vào thư mục input/.
3. Cập nhật TEXT_EVENTS nếu cần.
4. Chạy lệnh:
   ```
   python3 make_viral.py
   ```
5. Kiểm tra output ở thư mục output/.

---

## Tổng kết

- Cả 2 pipeline đều nhận input là video raw, audio, cấu hình JSON/Python dict.
- Output là video hoàn chỉnh (mp4), có thể kèm subtitle.
- Để AI khác sử dụng: chỉ cần chuẩn bị đúng input, gọi script chính, kiểm tra output.

Nếu cần chi tiết format input, ví dụ JSON hoặc TEXT_EVENTS, xem thêm file input.json (video-review) hoặc docs/USAGE_GUIDE.md (video-unbox).
