# Tài liệu Đặc tả Nghiệp vụ & Kiến trúc: Worker Translify

Tài liệu này cung cấp cái nhìn toàn diện và chính xác 100% về cơ chế hoạt động của `worker_translify`, được phân tách rõ ràng thành hai cấp độ: **Cấp Nghiệp vụ (Business Specification)** và **Cấp Kiến trúc (Architectural Specification)**.

---

## PHẦN I: ĐẶC TẢ CẤP NGHIỆP VỤ (BUSINESS SPECIFICATION)

### 1. Mục tiêu Nghiệp vụ (Business Objective)
Mục tiêu cốt lõi của `worker_translify` là tự động hóa toàn bộ quy trình **Việt hóa video ngắn quảng cáo/bán hàng** (Douyin/TikTok) từ Tiếng Trung sang Tiếng Việt. 

Hệ thống giải quyết các bài toán nghiệp vụ marketing thực tế:
- **Tái sử dụng nội dung (Anti-Reup):** Xóa bỏ các ký tự chữ cứng Tiếng Trung gốc trên video và thay thế bằng phụ đề Tiếng Việt động, giúp video đạt điểm kiểm duyệt cao trên các nền tảng mạng xã hội.
- **Tăng trải nghiệm bản địa (Localization):** Thay thế giọng thuyết minh Tiếng Trung bằng giọng đọc thuyết minh Tiếng Việt tự nhiên, trẻ trung kết hợp với nhạc nền gốc của video.
- **Khả năng chỉnh sửa cao (Editable):** Video được chuyển đổi thành cấu trúc dữ liệu lưu trong Database (Video-as-Data). Quá trình chỉnh sửa kịch bản dịch, thay đổi giọng đọc hoặc căn chỉnh thời gian có thể được thực hiện độc lập ở từng phân cảnh mà không cần chạy lại toàn bộ quy trình nặng nề từ đầu.
- **Kiểm soát chất lượng âm thanh (Constraint-Aware):** Ngăn chặn hiện tượng giọng đọc tiếng Việt bị tua nhanh quá mức (méo tiếng dạng chipmunk) do câu dịch dài hơn thời lượng thực tế của cảnh phim.

### 2. Quy trình Nghiệp vụ Đầu-Cuối (E2E Business Flow)
Quy trình nghiệp vụ của một lượt xử lý video diễn ra qua 5 bước chính:

```
[Nhập Video Gốc]
       │
       ▼
1. Cắt Phân Cảnh (Scene Segmentation)
       │
       ▼
2. Trích Xuất & Việt Hóa Lời Nói (Speech & OCR Translation)
       │
       ▼
3. Kiểm Soát Thời Lượng (Constraint Checking & LLM Rewrite)
       │
       ▼
4. Xử Lý Hình Ảnh & Giọng Đọc (Inpainting & Voiceover Generation)
       │
       ▼
5. Trộn Nhạc & Ghép Nối (Audio Mixing & Concat) ──> [Video Đầu Ra Hoàn Chỉnh]
```

1. **Phân đoạn Cảnh quay (Scene-first approach):** Video được tự động chia nhỏ thành các cảnh quay logic dựa trên sự thay đổi hình ảnh. Mọi thao tác xử lý sau đó đều áp dụng ở cấp độ cảnh độc lập.
2. **Nhận diện giọng nói & Dịch nghĩa:** Nhận diện lời thoại Tiếng Trung trong video gốc $\rightarrow$ dịch thuật sang Tiếng Việt có văn phong dynamic, bắt trend bán hàng.
3. **Quét chữ màn hình & Dịch tiêu đề:** Định vị tất cả các cụm chữ cứng xuất hiện trên màn hình $\rightarrow$ dịch nghĩa để chuẩn bị cho việc xóa và ghi đè phụ đề tiếng Việt.
4. **Kiểm duyệt & Tự động viết lại (Rewrite):** Hệ thống kiểm tra xem câu dịch Tiếng Việt có vượt giới hạn tốc độ nói tự nhiên hay không (**tối đa 4 từ/giây**). Nếu vượt quá, AI sẽ tự động viết ngắn câu dịch lại nhưng vẫn giữ nguyên thông điệp marketing cốt lõi.
5. **Tổng hợp & Ghép nối:** Tạo âm thanh tiếng Việt $\rightarrow$ co giãn thời gian khớp khít cảnh quay $\rightarrow$ trộn với âm thanh môi trường/nhạc nền gốc $\rightarrow$ xoá chữ Trung Quốc trên hình $\rightarrow$ đóng phụ đề Tiếng Việt $\rightarrow$ ghép nối các cảnh thành video hoàn chỉnh.

---

## PHẦN II: ĐẶC TẢ CẤP KIẾN TRÚC (ARCHITECTURAL SPECIFICATION)

`worker_translify` được thiết kế dưới dạng một Celery Worker độc lập, chạy trên môi trường hỗ trợ tăng tốc phần cứng NVIDIA GPU (CUDA).

### 1. Mô hình Dữ liệu (Pydantic Schema)
Mọi dữ liệu trung gian được định nghĩa chặt chẽ thông qua **Pydantic V2** tại [video_schema.py](file:///root/marketing-video-agent/worker_translify/model/video_schema.py):
- **`VideoProject`**: Thực thể gốc chứa `video_id` và danh sách `scenes`.
- **`Scene`**: Đại diện cho 1 cảnh quay, gồm:
  - `start`, `end`: Thời điểm bắt đầu và kết thúc (giây).
  - `speaker`: Bounding box của mặt khuôn mặt và cảm xúc.
  - `audio`: Chứa `zh_text` (gốc), `vi_text` (dịch), `duration`, `tts_file`.
  - `visual`: Chứa danh sách `ocr_text` dạng `OcrItem` (tọa độ bounding box, chữ gốc, chữ dịch).
  - `bgm`: Thể loại và âm lượng BGM.

### 2. Chi tiết các Module Kỹ thuật trong Pipeline

#### A. Analysis Engine (`translify_engine/analysis_engine.py`)
Thực hiện trích xuất dữ liệu đa phương tiện từ video gốc và điền vào Pydantic DB:
1. **Scene Detection:** Sử dụng `PySceneDetect` với thuật toán `ContentDetector(threshold=27.0)` để lấy danh sách mốc thời gian cảnh.
2. **Audio Demuxing:** Sử dụng FFmpeg với cờ `-hwaccel cuda` trích xuất track âm thanh gốc sang định dạng lossless WAV PCM mono, sample rate 16000Hz phục vụ cho Whisper.
3. **Vocal & BGM Separation:** Nạp thư viện `audio-separator` chạy model mạng MDX-Net ONNX (`UVR-MDX-NET-Inst_HQ_3.onnx`) trên GPU để phân tách sạch track giọng nói (`vocals.wav`) và nhạc nền gốc (`instrumental.wav`).
4. **ASR (Speech-to-Text):** Khởi tạo `faster-whisper` phiên bản model `small` chạy trên GPU (`device="cuda"`, `compute_type="int8"`) dịch giọng nói Trung Quốc thành văn bản có kèm timestamp, sau đó ánh xạ tọa độ thời gian vào từng Cảnh logic tương ứng.
5. **OCR Scanning:** Chụp ảnh video gốc với tần suất 1 khung hình/giây. Chạy `PaddleOCR` (chữ Trung Quốc) định vị tọa độ hộp văn bản (bounding boxes) và nhận dạng chữ cứng màn hình.
6. **AI Translation:** Gọi API cục bộ Ollama `/api/chat` (sử dụng model `qwen2.5:7b`, nhiệt độ `0.2`) để dịch toàn bộ phụ đề và tiêu đề OCR sang tiếng Việt trẻ trung, chuẩn marketing.

#### B. Constraint Engine (`translify_engine/constraint_engine.py`)
Đảm bảo tính đồng bộ hóa thời gian và ngăn ngừa méo tiếng:
1. **Kiểm tra giới hạn (Word-per-second limit):**
   - Đếm số lượng từ của câu dịch Tiếng Việt: `word_count = len(vi_text.split())`.
   - Tính toán ngân sách từ tối đa: `max_words = max(1, int(duration * 4.0))`.
2. **AI Rewrite Layer:**
   - Nếu `word_count > max_words`, hệ thống kích hoạt Ollama gọi model `qwen2.5:7b` để viết lại câu.
   - Sử dụng System Prompt chuyên dụng ép buộc AI rút gọn câu chữ về dưới ngưỡng `{max_words}` nhưng nghiêm cấm làm thay đổi ý nghĩa bán hàng.
   - **Cơ chế Fallback an toàn:** Nếu kết nối Ollama thất bại, hệ thống tự động sử dụng hàm cắt chuỗi Python để lấy đúng `{max_words}` từ đầu tiên, đảm bảo pipeline không bị gián đoạn.

#### C. Composition & Assembly Engine (`translify_engine/phase3_compose.py`)
Module chịu trách nhiệm chính trong việc xử lý hình ảnh, âm thanh và kết hợp toàn bộ tài nguyên để xuất video Việt hóa hoàn chỉnh. Được thiết kế lại toàn diện theo chuẩn hướng đối tượng (OOP) và kiến trúc cấu hình mở rộng:

1. **Kiến trúc Cấu hình Hợp nhất (`CompositionConfig`):**
   - **`VoiceoverConfig`**: Định nghĩa sample rate (mặc định 16000Hz), giọng đọc (`vi-VN-NamMinhNeural`), giới hạn co giãn [0.5x, 2.0x], ngưỡng lệch 5%, và giới hạn luồng song song.
   - **`InpaintConfig`**: Cấu hình sử dụng AI LaMa, padding mở rộng 6px và thiết bị chạy (CUDA/CPU).
   - **`AssemblyConfig`**: Cấu hình âm lượng phối (BGM giảm -12dB), định dạng codec (h264_nvenc / libx264), bitrate âm thanh 192k, tần số phối 44100Hz và các presets.

2. **Xử lý Bất đồng bộ Song song (`VoiceoverGenerator`):**
   - Khởi tạo tiến trình sinh giọng nói tiếng Việt từ `edge-tts` bất đồng bộ hoàn toàn.
   - Sử dụng **`asyncio.Semaphore(5)`** để giới hạn số luồng TTS song song, ngăn ngừa lỗi nghẽn hoặc bị chặn IP (Rate Limit) bởi Edge-TTS API.
   - Tách biệt pha I/O mạng bất đồng bộ khỏi pha xử lý âm thanh đồng bộ: sau khi tải xong toàn bộ các phân đoạn giọng nói, hệ thống mới tiến hành chuyển đổi WAV, co giãn thời lượng (**Rubberband co-stretching**) để khớp chính xác từng miligiây với cảnh phim và vá mảng tĩnh (silent padding).
   - Tích hợp bộ chạy luồng an toàn (Standard ThreadPool Executor fallback) khi được kích hoạt bên trong một event loop đang chạy (như Celery worker), ngăn ngừa xung đột loop.

3. **Xóa chữ cứng màn hình thông minh (`TextInpainter`):**
   - Quản lý tài nguyên an toàn: Toàn bộ quá trình xử lý OpenCV (`VideoCapture`, `VideoWriter`) được bao bọc trong khối `try-finally` chặt chẽ để đảm bảo không bị rò rỉ bộ nhớ hoặc khóa file khi có ngoại lệ xảy ra.
   - Tẩy chữ cứng: Tạo mask nhị phân từ tọa độ bounding box OCR nới rộng 6 pixel.
   - Áp dụng mô hình AI tiên tiến **IOPaint LaMa** trên GPU CUDA (hoặc tự động fallback sang thuật toán OpenCV Telea tốc độ cao nếu GPU thiếu VRAM hoặc IOPaint bị tắt).
   - Mã hóa tăng tốc GPU NVENC để chuyển đổi video thô sang chuẩn H.264 MP4 không tiếng.

4. **Biên tập & Kết xuất Sản phẩm Cuối (`VideoAssembler`):**
   - Đóng gói logic thực thi FFmpeg qua bộ hàm helper an toàn, tự động ghi nhận log stderr và stdout chi tiết khi câu lệnh biên tập thất bại để tối ưu hóa việc giám sát lỗi.
   - Thực hiện phối âm (Audio Mixing) hai kênh: Giảm âm lượng nhạc nền gốc (BGM) xuống mức `0.25` và trộn với track thuyết minh tiếng Việt rõ ràng.
   - Đốt cứng phụ đề nghệ thuật (ASS Subtitle Burn) động qua bộ lọc `ass` của FFmpeg.
   - Render tốc độ cao với card đồ họa NVIDIA (RTX 3060) qua codec `h264_nvenc` với các tham số tối ưu (`-preset p5`, `-rc vbr`, `-cq 20`).
   - Tự động kích hoạt **Cơ chế dự phòng CPU (CPU Fallback)** sang codec `libx264` (`-preset veryfast`, `-crf 20`) nếu phát hiện lỗi hoặc không hỗ trợ phần cứng GPU NVENC trên môi trường chạy hiện tại.

*Lưu ý: Hệ thống cũng cung cấp lớp `RenderEngine` (`translify_engine/render_engine.py`) phục vụ như một giải pháp thay thế để chia nhỏ và render độc lập từng scene thô rồi ghép nối tiếp (concat).*

---

### 3. Tích hợp Celery Task & Dòng lệnh (CLI)
Hệ thống cung cấp hai phương thức kích hoạt có chung một luồng logic:
- **CLI (`__main__.py`)**: Dùng cho thử nghiệm cục bộ thông qua lệnh:
  ```bash
  PYTHONPATH=worker_translify python3 -m worker_translify --input <input.mp4> --output <output.mp4> --work-dir <dir>
  ```
- **Celery Worker (`celery_worker.py`)**: Kết nối với hàng đợi tin nhắn Redis/RabbitMQ để tiêu thụ các tác vụ phân tán, liên kết trực tiếp các API dịch vụ bên ngoài vào hệ thống xử lý video-as-data.
