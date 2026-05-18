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

#### C. Render Engine (`translify_engine/render_engine.py`)
Chịu trách nhiệm xử lý hình ảnh, âm thanh độc lập ở từng cảnh quay trước khi ghép nối:
1. **OpenCV Telea Inpainting:** 
   - Với mỗi cảnh có chữ cứng Trung Quốc, duyệt qua từng khung hình (frames).
   - Tạo mặt nạ nhị phân (mask) từ tọa độ bounding box của OCR (được nới rộng 6 pixel biên để tẩy triệt để).
   - Thực hiện thuật toán xóa chữ tốc độ cao `cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)`.
   - Transcode clip sạch sang chuẩn H.264 MP4 không tiếng bằng FFmpeg (`-c:v libx264 -pix_fmt yuv420p -an`).
2. **TTS Synthesis:**
   - Gọi thư viện `edge-tts` bất đồng bộ để sinh giọng đọc Việt Nam (mặc định giọng `vi-VN-NamMinhNeural`).
   - Có cơ chế **Retry 3 lần** kết hợp thời gian trễ tăng dần lũy thừa (exponential backoff) nếu gặp sự cố mạng.
3. **Timing Co-Stretching (Rubberband):**
   - Đọc file âm thanh TTS tạm bằng `soundfile`.
   - So sánh thời lượng âm thanh thực tế thu được (`actual_dur`) với thời lượng phân cảnh (`scene_dur`).
   - Tính toán tỷ lệ co giãn `ratio = actual_dur / scene_dur`. Tỷ lệ này được giới hạn chặt chẽ trong khoảng an toàn `[0.5, 2.0]`.
   - Nếu tỷ lệ sai lệch quá 5%, nạp thuật toán co giãn tốc độ giữ nguyên cao độ âm thanh **Rubberband** (`pyrubberband.time_stretch`).
   - Cắt ngắn hoặc chèn thêm mảng giá trị 0 (silent padding) để thời lượng file âm thanh đầu ra khớp khít từng miligiây với cảnh phim.
4. **Stylized Subtitle Burn:**
   - Tạo file phụ đề nghệ thuật `.ass` động từ câu dịch bằng `subtitle_utils.py` (font mặc định `Outfit`, cỡ chữ `32`, màu chữ trắng viền đen dày).
   - Ghi đè trực tiếp phụ đề lên clip sạch bằng FFmpeg video filter: `-vf ass=subtitle.ass`.
5. **Audio Mixing:**
   - Cắt nhạc nền gốc tương ứng với khoảng thời gian của cảnh từ file `full_audio.wav`.
   - Sử dụng FFmpeg mix track giọng đọc tiếng Việt và nhạc nền gốc ở tỷ lệ âm lượng nhạc nền là 0.3 (`-filter_complex "[1:a]volume=0.3[bgm];[0:a][bgm]amix=inputs=2:duration=first[aout]"`).
6. **Lossless Scene Concatenation:**
   - Tập hợp tất cả các file phân cảnh hoàn chỉnh `.mp4` vào danh sách.
   - Sử dụng FFmpeg `concat` demuxer ghép nối nối tiếp không nén để xuất ra video đích hoàn thiện mà không gây ra hiện tượng giật hình hoặc mất đồng bộ.

---

### 3. Tích hợp Celery Task & Dòng lệnh (CLI)
Hệ thống cung cấp hai phương thức kích hoạt có chung một luồng logic:
- **CLI (`__main__.py`)**: Dùng cho thử nghiệm cục bộ thông qua lệnh:
  ```bash
  PYTHONPATH=worker_translify python3 -m worker_translify --input <input.mp4> --output <output.mp4> --work-dir <dir>
  ```
- **Celery Worker (`celery_worker.py`)**: Kết nối với hàng đợi tin nhắn Redis/RabbitMQ để tiêu thụ các tác vụ phân tán, liên kết trực tiếp các API dịch vụ bên ngoài vào hệ thống xử lý video-as-data.
