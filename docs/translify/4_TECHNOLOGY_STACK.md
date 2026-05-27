# Hồ Sơ Công Nghệ & AI Models: Worker Translify (Technology Profile)

Động cơ **Worker Translify** được xây dựng trên nền tảng các công nghệ SOTA (State-of-the-Art) tiên tiến nhất hiện nay trong các lĩnh vực thị giác máy tính (Computer Vision), xử lý ngôn ngữ tự nhiên (NLP) và xử lý tín hiệu âm thanh (Audio Processing).

Dưới đây là mô tả chi tiết về cấu hình, thông số vận hành và lý do lựa chọn từng công nghệ cốt lõi trong hệ thống.

---

## 1. Bản Đồ Phân Phối Tài Nguyên GPU (GPU VRAM Allocation Map)

Hệ thống được tối ưu hóa đặc biệt để chạy mượt mà trên các card đồ họa NVIDIA phổ thông (ví dụ **RTX 3060 12GB** hoặc **RTX 4060 Ti 16GB**) thông qua việc dọn rác GPU chủ động (`clean_gpu_memory`) và chạy tiến trình phụ cô lập:

| Tên Module AI / Thư Viện | Mô Hình / Model | Tài Nguyên GPU / VRAM | Lý do lựa chọn & Vai trò kỹ thuật |
| :--- | :--- | :--- | :--- |
| **Vocal Separation** | `UVR-MDX-NET-Inst_HQ_3.onnx` (MDX-Net) | **~1.5 GB VRAM** | Phân tách nhạc nền gốc (BGM) và giọng thoại thuyết minh Trung Quốc sạch nhất thế giới. |
| **Speech-To-Text (ASR)**| `faster-whisper` (Model `small` / `large-v3` INT8) | **~3.0 GB VRAM** | Nhận diện giọng thuyết minh Trung Quốc và trả về chính xác timestamp đến mili-giây. |
| **Text Detection** | `paddlex` / `PaddleOCR` (`PP-OCRv4_mobile_det`) | **~1.0 GB VRAM** (Bản CPU-fallback) | Phát hiện tọa độ đa giác chữ cứng tiếng Trung trên hình với độ trễ tối thiểu (chỉ dùng Det-only). |
| **Video Inpainting** | **ProPainter (SOTA Video Inpainting)** | **~4.5 GB - 8.0 GB VRAM** (Tùy theo chunk) | Lấp đầy vùng chữ bị che bằng điểm ảnh tự nhiên trích xuất từ quá khứ/tương lai của clip. |
| **Local LLM Engine** | Ollama (`qwen2.5:7b` INT4) | **~4.8 GB VRAM** (Nạp vào RAM hệ thống) | Dịch thuật văn cảnh ngữ nghĩa tự nhiên và tự động viết lại rút gọn khống chế thời lượng. |

---

## 2. Đi Sâu Chi Tiết Từng Công Nghệ Học Sâu (Deep Learning Deep-Dive)

### A. Phân Tách Âm Thanh: UVR MDX-Net ONNX
- **File:** `model/UVR-MDX-NET-Inst_HQ_3.onnx`
- **Nguyên lý:** Mô hình MDX-Net sử dụng mạng tích chập đa tần số để tách nhạc nền gốc khỏi âm thoại mà không để lại các tiếng rè hay tạp âm cơ học (artifacts).
- **Lý do lựa chọn:** Đây là mô hình đạt giải nhất trong cuộc thi tách âm thanh quốc tế (Ultimate Vocal Remover - UVR). Giúp giữ nguyên vẹn 100% âm thanh môi trường và nhạc nền gốc của video Douyin, đảm bảo tính sống động của clip sau khi chèn giọng đọc Việt.

### B. Nhận Dạng Giọng Nói: Faster-Whisper
- **Lý do lựa chọn:** Standard Whisper của OpenAI thường chạy rất chậm và tiêu tốn nhiều VRAM. `faster-whisper` là bản thiết kế lại sử dụng công cụ suy luận **CTranslate2**, giúp tăng tốc độ xử lý nhanh gấp **4 lần** so với Whisper gốc, đồng thời áp dụng lượng tử hóa `int8` giúp giảm tải 60% bộ nhớ GPU.
- **Tham số vận hành:** Khởi chạy với model `small` trên GPU CUDA, bắt buộc ngôn ngữ nhận diện là tiếng Trung (`zh`), sử dụng `beam_size=5` giúp tăng độ chính xác của các đoạn hội thoại bán hàng.

### C. Phát Hiện Biên Chữ: PaddleOCR PP-OCRv4
- **Lazy det-only bypass REC:** PaddleOCR tiêu chuẩn thường cố gắng kiểm tra mạng và tự động tải mô hình Nhận diện chữ (`rec`) từ máy chủ Baidu, gây ra hiện tượng nghẽn mạng và treo ứng dụng (startup delay) lên tới vài phút. Translify giải quyết bằng cách cấu hình **`rec=False`** và chỉ sử dụng lớp Phát hiện biên chữ (`detector-only`) để thu về bounding box tọa độ chữ.
- **Tuned Box Parameters:**
  - `det_db_unclip_ratio=1.15` (Nén chặt vùng biên giúp mặt nạ mask ôm khít lấy nét chữ, không bị dư thừa pixel nền).
  - `det_db_thresh=0.35` (Bỏ qua các vùng nhiễu mờ nhạt).
  - `det_db_box_thresh=0.6` (Chỉ chấp nhận các cụm chữ rõ nét tự tin).

### D. Xóa Chữ Video Thông Minh: SOTA ProPainter
- **Nguyên lý:** Khác với inpainting dạng tĩnh (như LaMa chỉ xem xét 1 khung hình đơn lẻ gây ra hiện tượng méo hình/rung giật khi chạy video), **ProPainter** sử dụng cơ chế Attention kép (Dual Attention) kết hợp dòng quang học (Optical Flow) để tìm kiếm các điểm ảnh sạch bị che khuất ở các khung hình trước hoặc sau đó để đắp vào khung hình hiện tại.
- **Lý do lựa chọn:** Đây là công nghệ SOTA hàng đầu thế giới về Video Inpainting, giúp video sau khi xóa chữ tiếng Trung đạt độ tự nhiên tuyệt đối, tiệp màu nền hoàn hảo, không có vết nhòe mờ (blur).

### E. Co Giãn Tần Số Âm Thanh: Rubberband
- **Lý do lựa chọn:** Khi co giãn thời lượng âm thanh bằng FFmpeg thông thường (`atempo` filter), giọng nói thường bị biến dạng và mất tự nhiên. Translify sử dụng **Rubberband** (thông qua CLI `rubberband-cli` và thư viện wrapper `pyrubberband`), thuật toán phân tích phổ tần số âm thanh chuyên nghiệp thế giới, cho phép tăng hoặc giảm tốc độ nói trong ngưỡng an toàn `[0.5x, 2.0x]` mà **không hề làm thay đổi tông/pitch** của giọng đọc tiếng Việt.

### F. Dịch Thuật Cục Bộ: Ollama & Qwen-2.5-7B
- **Lý do lựa chọn:** Đảm bảo bảo mật tuyệt đối dữ liệu kịch bản bán hàng của doanh nghiệp (không gửi ra API đám mây bên thứ ba). 
- Model **Qwen-2.5-7B** được tối ưu hóa đặc biệt về khả năng song ngữ Trung - Việt, hiểu rõ văn cảnh trẻ trung, bắt trend và đặc biệt nhanh nhạy trong việc rút gọn câu chữ khi chạy engine khống chế thời lượng (constraint rewrite layer).

---

## 3. Bản Đồ Công Nghệ Lập Trình & Codebase Stack

```
[Môi trường vận hành] ──> WSL2 Ubuntu / Linux (GPU CUDA Tăng tốc phần cứng)
     │
[Ngôn ngữ lập trình] ──> Python 3.10+ (Đóng gói Celery Worker phân tán)
     │
[Xử lý Video/Hình ảnh] ─> FFmpeg 6.0 (Mã hóa NVENC GPU & libass filter) / OpenCV 4.8
     │
[Xử lý Dữ liệu] ───────> Pydantic V2 Schema (Chuẩn hóa JSON Video-as-Data)
```

- **Pydantic V2 Validation:** Bảo vệ toàn vẹn luồng dữ liệu trung gian, tự động định kiểu dữ liệu cho OCR bounding boxes, kiểm tra kiểu dữ liệu đầu vào của các cảnh quay và xuất bản file cấu hình `project_db.json` sạch lỗi chỉ mục.
- **FFmpeg libass filter:** Cho phép vẽ phụ đề chuẩn vector động với tốc độ cực nhanh trên GPU, hỗ trợ các hiệu ứng karaoke, micro-subs chuyển động mượt mà.
