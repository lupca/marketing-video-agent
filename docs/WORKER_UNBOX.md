# Hướng Dẫn: Plugin Video Unbox

Công cụ **Worker Unbox** được thiết kế đặc biệt cho dạng Video Viral, Music Sync. Hệ thống hỗ trợ 2 loại Worker Unbox chuyên biệt:

1. **Basic Unbox** (`unbox` job type) - Cắt ghép beat-sync cổ điển từ nhiều clip ngắn.
2. **Viral Unbox** (`unbox_viral` job type) - AI Smart Editor tự động phân tích chuyển động, bám vật thể, speed-ramp và lồng tiếng ASMR.

---

## 1. So Sánh Hai Chế Độ Worker Unbox

| Tính năng | 📦 Basic Unbox (`unbox`) | ⚡ Viral Unbox (`unbox_viral`) |
| :--- | :--- | :--- |
| **Hàm xử lý chính** | `make_viral.py` (sử dụng `video_viral.py`) | `unbox_viral.py` (sử dụng `video_unbox.py`) |
| **Nguyên liệu Video** | Nhiều clips ngắn thô khác nhau. | **1 Clip dài duy nhất** (1.5 - 3 phút) chứa trọn vẹn quá trình unbox. |
| **Nhận diện & Crop 9:16** | Center crop tĩnh (luôn cắt chính giữa khung hình). | **YOLO Smart Crop:** Nhận diện bàn tay/sản phẩm qua YOLOv8 (`yolov8n.pt`) để di chuyển vùng crop theo vật thể. |
| **Tua nhanh/chậm (Speed)** | Giữ nguyên tốc độ gốc 1x. | **Optical-Flow Speed Ramping:** Tua nhanh phần tĩnh (`STATIC`) và làm chậm (`DYNAMIC`) phần có hành động bóc seal/mở hộp. |
| **Trộn âm thanh (Audio)** | Lồng đè nhạc nền (BGM) lên toàn bộ clip. | **ASMR + BGM Mix:** Tách âm thanh ASMR gốc của video rồi trộn đều bám theo beat của nhạc nền. |
| **Đè chữ (Text Overlay)** | Bắt buộc điền exact **Timestamp (giây)** cho từng event. | **Auto Beat-Snapped:** Không cần điền time; chữ tự động nhảy khớp vào các nhịp drop mạnh của nhạc. |

---

## 2. Cơ chế Hoạt Động Kỹ Thuật

Đây là một Engine render sử dụng FFmpeg xử lý luồng Video kết hợp thư viện `librosa` xử lý Audio.

### A. Quy trình xử lý của Basic Unbox
1. **Phát hiện Beat (Beat-drop detect)**: `librosa` phân tích File âm thanh MP3 đầu vào để tạo danh sách mốc thời gian beat-drop mạnh.
2. **Nối Scene bằng Hiệu Ứng**: Nối các clip ngắn thô bám theo beat drop, xfade chuyển tiếp cảnh kết hợp zoom trượt nhẹ (Ken Burns).
3. **Overlay Text (Chữ Tốc Độ)**: Lồng chữ theo đúng số giây được quy định trong cấu hình `text_events`.

### B. Quy trình xử lý của Viral Unbox
1. **Trích xuất ASMR**: Tách âm thanh gốc (ASMR) từ clip chính.
2. **Phân tích Chuyển động (Motion Analysis)**: Tính toán Optical Flow của video để phân biệt các đoạn tĩnh, lặp lại và động.
3. **Tracking Sản Phẩm (YOLO Smart Crop)**: Chạy model YOLOv8n trên frame để xác định tọa độ trung tâm của sản phẩm/tay người, tạo ra đường track trượt crop 9:16 mượt mà.
4. **Speed Ramping & Render Segments**: Dựa trên phân tích chuyển động và beat nhạc để quyết định tốc độ tua (vừa bám nhạc vừa làm nổi bật hành động bóc seal).
5. **Auto Text Sync**: Phân bổ các text events vào các beat drop trống đảm bảo khoảng cách tối thiểu 2.0s để không đè chữ.
6. **Mux Audio**: Trộn âm thanh gốc đã đồng bộ tốc độ với nhạc nền BGM bám theo beat và xuất video output.

---

## 3. Cấu hình Input & Payload

### A. Basic Unbox Config Data
```json
{
  "clips": [
    "s3://videos/assets/unbox/clip1.mov",
    "s3://videos/assets/unbox/clip2.mov"
  ],
  "audio": "s3://videos/assets/audio/music.mp3",
  "text_events": [
    {"time": 0.0, "text": "ĐẬP HỘP VỢT CAO CẤP 🔥", "effect": "hook"},
    {"time": 3.2, "text": "Khung Carbon siêu nhẹ", "effect": "feature"}
  ]
}
```

### B. Viral Unbox Config Data
```json
{
  "video": "s3://videos/assets/unbox/raw_one_take.mp4",
  "audio": "s3://videos/assets/audio/trending_phonk.mp3",
  "text_events": [
    {"text": "SIÊU PHẨM CẦU LÔNG 📦", "effect": "hook"},
    {"text": "Bóc seal cực đã tay", "effect": "feature"},
    {"text": "Giá cực hời trong bio!", "effect": "feature"}
  ]
}
```

---

## 4. Tinh Chỉnh Nâng Cao (Dành cho Developer)

Khi điều chỉnh Source hệ thống trong `worker_unbox/unbox_engine/`:

- **Tăng tốc độ luân chuyển Scene**: 
  Giảm `xfade_duration` (Mặc định 0.5s) xuống `0.2s - 0.4s` tạo nét cắt gắt. Hoặc giảm biến thời gian `scene_max_seconds`.
- **Thay Tốc Độ Zoom (Ken Burns)**:
  Bên trong hàm `_render_scene()`, thay đổi hệ số trượt `z='min(zoom+0.0015,1.15)'`. Phóng to `0.0018` dồn dập, `0.0012` êm trôi.
- **Render Output Bị Lỗi (Giật Lag)**:
  Có thể do Drop Rate khung hình ảo khi FFmpeg scale. Giữ nguyên force Output Filter: `s=1080x1920:fps=30` trước khi qua Zoompan.
- **Thiếu FFmpeg Drawtext Backend**:
  Module tự bắt `OverlayError` để đổi qua Fallback chạy MoviePy/Pillow Render Text dán đè thay nếu OS Developer không build bản có Drawtext.
