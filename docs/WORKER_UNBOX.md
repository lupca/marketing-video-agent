# Hướng Dẫn: Plugin Video Unbox

Công cụ **Worker Unbox** được thiết kế đặc biệt cho dạng Video Viral, Music Sync. Hệ thống sẽ tự động bắt cảnh quay cắt ghép nối tiếp nhau khớp từng nhịp đập âm nhạc (Beat-drop sync).

## 1. Cơ chế Hoạt Động Kỹ Thuật

Đây là một Engine render sử dụng FFmpeg xử lý luồng Video kết hợp thư viện `librosa` xử lý Audio.

1. **Phát hiện Beat (Beat-drop detect)**
   `librosa` phân tích File âm thanh MP3 đầu vào để tạo danh sách mốc thời gian beat-drop mạnh.
2. **Cắt mượt & Loại bỏ Silence**
   Tìm ngưỡng im lặng `silence_db` trong các File Clip thô `.mov`, auto cắt bỏ đoạn chết (Trim đầu/cuối), và chuẩn hóa khung hình dọc `1080x1920@30fps`.
3. **Lên Kế Hoạch Scene (Scene Planning)**
   Cắt scene (cảnh) bám theo Beat hoặc Random planning trong khoảng Min/Max `[scene_min_seconds, scene_max_seconds]`.
4. **Nối Scene bằng Hiệu Ứng**
   `xfade` để thay đổi qua lại giữa cảnh. Hỗ trợ luân phiên hiệu ứng như `fade`, `slideleft` liên tục.
   Hiệu ứng Ken Burns (Zoom trượt êm ái x/y) chạy mặc định tạo nhịp độ sống động.
5. **Overlay Text (Chữ Tốc Độ)**
   Render nội dung chữ (Hook, Lợi ích Feature) bằng FFmpeg `drawtext` đè nháy ngay điểm quan trọng.

## 2. Dữ liệu Input & Config 

Dữ liệu do API truyền xuống là mảng `config_data`:

```json
{
  "clips": [
    "s3://videos/assets/unbox/clip1.mov",
    "s3://videos/assets/unbox/clip2.mov"
  ],
  "audio": "s3://videos/assets/audio/the_mountain-tiktok.mp3",
  "text_events": [
    {"time": 0.0, "text": "VỢT CẦU LÔNG SIÊU ĐỈNH", "effect": "hook"},
    {"time": 3.2, "text": "Cuốn cán chính hãng", "effect": "feature"}
  ]
}
```

## 3. Tinh Chỉnh Nâng Cao (Dành cho Developer)

Khi điều chỉnh Source hệ thống trong `make_viral.py`:

- **Tăng tốc độ luân chuyển Scene**: 
  Giảm `xfade_duration` (Mặc định 0.5s) xuống `0.2s - 0.4s` tạo nét cắt gắt. Hoặc giảm biến thời gian `scene_max_seconds`.
- **Thay Tốc Độ Zoom (Ken Burns)**:
  Bên trong hàm `_render_scene()`, thay đổi hệ số trượt `z='min(zoom+0.0015,1.15)'`. Phóng to `0.0018` dồn dập, `0.0012` êm trôi.
- **Render Output Bị Lỗi (Giật Lag)**:
  Có thể do Drop Rate khung hình ảo khi FFmpeg scale. Giữ nguyên force Output Filter: `s=1080x1920:fps=30` trước khi qua Zoompan.
- **Thiếu FFmpeg Drawtext Backend**:
  Module tự bắt `OverlayError` để đổi qua Fallback chạy MoviePy/Pillow Render Text dán đè thay nếu OS Developer không build bản có Drawtext.
