# Tài Liệu Kỹ Thuật - make_viral.py

## 1) Mục tiêu
Tài liệu này giải thích kiến trúc, luồng xử lý và các điểm cần quan tâm khi bảo trì module [make_viral.py](../make_viral.py).

Pipeline gồm 4 phần:
1. Phát hiện beat-drop từ file nhạc (librosa)
2. Cắt scene theo beat + trim silence + chuẩn hóa 9:16
3. Nối scene bằng xfade và mux audio
4. Text overlay (hook + feature) bằng FFmpeg drawtext hoặc MoviePy/Pillow

## 2) Kiến trúc tổng quan

### Entry point
- `main()` trong [make_viral.py](../make_viral.py) điều phối toàn bộ pipeline.

### Khối phát hiện beat
- `detect_beat_drops(mp3_path, ...)` tạo danh sách mốc thời gian beat-drop.
- Đầu vào: file MP3
- Đầu ra: `list[float]` (giây)

### Khối render video
- `class VideoViralEngine`
- Trách nhiệm:
  - Phân tích độ dài clip + trim đầu/cuối im lặng
  - Lập kế hoạch scene (random hoặc beat-synced)
  - Render từng scene 1080x1920@30
  - Nối scene qua xfade
  - Mux audio TikTok vào video silent

### Khối overlay text
- `overlay_text(...)`
- Tự động chọn backend:
  - FFmpeg drawtext nếu có hỗ trợ
  - MoviePy/Pillow nếu drawtext không có

## 3) Dữ liệu và cấu hình chính
Các biến cấu hình top-level trong [make_viral.py](../make_viral.py):
- `INPUT_DIR`: thư mục input
- `OUTPUT_DIR`: thư mục output
- `RAW_CLIPS`: danh sách `*.mov`
- `TIKTOK_MP3`: file audio nền
- `TEXT_EVENTS`: lịch hiển thị text

Tham số quan trọng trong `VideoViralEngine(...)`:
- `scene_min_seconds`, `scene_max_seconds`: khoảng độ dài scene
- `silence_db`, `silence_min_seconds`: ngưỡng trim silence
- `fps`, `crf`, `preset`: chất lượng/tốc độ encode
- `beat_drop_times`: bật beat-sync planning
- `audio_track`: file audio để mux
- `workers`: số lượng worker render song song

## 4) Luồng xử lý chi tiết
1. `main()` gọi `detect_beat_drops(TIKTOK_MP3)`
2. Tạo engine, gọi `engine.build(stage2)`
3. Trong `build()`:
   - `_analyze_inputs()` -> `_analyze_one()` -> `_probe_duration()` + `_detect_trim_bounds()`
   - `_build_scene_plan()` -> `_plan_beat_synced()` hoặc `_plan_random()`
   - `_render_scenes()` -> `_render_scene()`
   - `_concat_scenes()` (xfade)
   - `_mux_audio()` nếu có `audio_track`
4. `overlay_text(stage2, final, TEXT_EVENTS, ...)`
5. Xóa file tạm stage2

## 5) Các quyết định kỹ thuật quan trọng

### 5.1 Beat-sync planning
- `_beat_durations()` tạo các segment theo beat trong range `[scene_min_seconds, scene_max_seconds]`.
- `_plan_beat_synced()` đã có cơ chế spill-over qua clip tiếp theo để không bỏ sót clip cuối.

### 5.2 Render scene với Ken Burns
- `_render_scene()` sử dụng chain:
  - `scale` + `crop` -> 9:16
  - `zoompan` center zoom
- Mục tiêu zoom:
  - Zoom chậm: `z='min(zoom+0.0015,1.15)'`
  - Tâm zoom: `x='iw/2-(iw/zoom)/2'`, `y='ih/2-(ih/zoom)/2'`
- Jitter-free:
  - Cố định output `s=1080x1920`, `fps=30` trong zoompan

### 5.3 Concat scene với transition
- `_concat_scenes()` dùng `xfade` chain thay vì concat copy.
- Hiệu ứng luân phiên: `fade`, `slideleft`.
- `xfade_duration` đang để 0.5s để chuyển cảnh mềm và không quá nhanh.

### 5.4 Overlay text fallback
- Nếu FFmpeg không có `drawtext`, tự động fallback sang MoviePy/Pillow.
- Điều này giúp pipeline vẫn chạy trên máy macOS không build freetype.

## 6) Error handling
Custom exceptions:
- `FFmpegNotFoundError`: thiếu ffmpeg/ffprobe
- `VideoProcessingError`: lỗi command ffmpeg/ffprobe
- `OverlayError`: lỗi overlay text

Khi debug, ưu tiên đọc `stderr` trong message của `VideoProcessingError`.

## 7) Hướng dẫn bảo trì (maintenance checklist)

### Mỗi lần thay đổi pipeline
1. Chạy syntax check:
   - `python3 -m py_compile make_viral.py`
2. Chạy E2E:
   - `python3 make_viral.py`
3. Verify output:
   - `ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,codec_type:format=duration,size -of default=noprint_wrappers=1 output/viral_final.mp4`

### Khi cảnh bị nhanh/chậm quá
- Điều chỉnh:
  - `scene_min_seconds`, `scene_max_seconds`
  - `xfade_duration` trong `_concat_scenes()`

### Khi output bị rung/giật
- Kiểm tra trong `_render_scene()`:
  - `zoompan ... :s=1080x1920:fps=30`
  - Không bỏ `s`/`fps` trong zoompan

### Khi thiếu clip cuối
- Kiểm tra logic spill-over trong `_plan_beat_synced()`.

## 8) Mở rộng an toàn
- Thêm hiệu ứng xfade khác: update danh sách `effects` trong `_concat_scenes()`
- Thêm profile output: trích tham số encode ra config section
- Thêm telemetry: log tổng số scene, tổng duration, coverage
- Tách file theo module nếu code tiếp tục phình to:
  - `beat_sync.py`
  - `engine.py`
  - `overlay.py`
  - `main.py`

## 9) Performance notes
- Render đã sử dụng `ThreadPoolExecutor`.
- `workers` cao quá có thể nghẽn IO/CPU; trên M4 16GB, thường 3-4 là hợp lý.
- `preset` nhanh hơn sẽ render nhanh nhưng chất lượng/size thay đổi.

## 10) Quick map symbol -> trách nhiệm
- `detect_beat_drops`: tìm mốc beat-drop
- `VideoViralEngine.build`: điều phối render scene -> concat -> mux
- `_plan_beat_synced`: chia scene theo beat, đảm bảo không bỏ clip
- `_render_scene`: scale/crop + Ken Burns zoom
- `_concat_scenes`: xfade transitions
- `overlay_text`: text layer và fallback backend
