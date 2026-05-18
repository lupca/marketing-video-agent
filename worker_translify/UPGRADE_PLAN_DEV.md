# BẢN THIẾT KẾ KỸ THUẬT NÂNG CẤP (DEV PLAN)
**Dự án:** Translify Pipeline (Video Marketing Automation)
**Mục tiêu:** Tích hợp RVC Voice Cloning và Tối ưu hóa FFmpeg Anti-Reup

---

## 🛠️ Hạng mục 1: Tích hợp RVC (Retrieval-based Voice Conversion)

Chúng ta sẽ sử dụng kiến trúc ghép nối (Pipeline Chaining): **Edge-TTS (Tạo phát âm chuẩn) -> RVC (Phủ âm sắc KOC) -> Rubberband (Khớp thời gian)**. 

### 1. Luồng xử lý (Workflow)
*   **Bước 1:** `phase3_compose.py` tiếp tục sử dụng hàm `tts_generate_segment` (Edge-TTS) để tạo ra các file giọng đọc `.wav` thô mang âm điệu tiếng Việt chuẩn (Giọng Nam/Nữ).
*   **Bước 2:** Xây dựng một hàm mới `rvc_convert(input_wav, output_wav, rvc_model_path)`. Hàm này sẽ gọi CLI hoặc thư viện của RVC để chuyển đổi `input_wav` (từ Edge-TTS) thành âm thanh mang chất giọng của người Trung Quốc (đã được train sẵn thành file `.pth`).
*   **Bước 3:** Chuyển `output_wav` của RVC vào thuật toán `rubberband` hiện có để co giãn thời gian khớp với độ dài video gốc.

### 2. Cần chuẩn bị (Dependencies)
*   Tích hợp gói mã nguồn mở `rvc-cli` (hoặc module python tương đương) vào thư mục `worker_translify`.
*   Tạo thư mục `model/rvc_models/` để chứa các file mô hình `.pth` và `.index` của các KOC gốc.
*   Cài đặt môi trường Python tương thích: Cập nhật `requirements.txt` với `torch`, `torchaudio`, `fairseq`, `librosa`...

### 3. Sửa đổi Code
*   **`phase3_compose.py`**: Chèn đoạn code gọi hàm RVC ngay sau khi file Edge-TTS được tải về thành công, và thay thế input của block `pyrb.time_stretch` bằng file đầu ra từ RVC.

---

## ✂️ Hạng mục 2: Kỹ thuật Lách Thuật Toán (Anti-Reup FFmpeg Filters)

Thực hiện chỉnh sửa trực tiếp bên trong bước cuối của `phase3_compose.py` (hàm `assemble_final_video`). Chúng ta sẽ tận dụng FFmpeg Filter Complex để xử lý trực tiếp hình ảnh/âm thanh trên GPU (`h264_nvenc`).

### Các thông số Filter FFmpeg cần tích hợp:
Sẽ xử lý trên luồng hình ảnh video gốc (`[0:v]`).

1. **TRIM (Cắt đầu đuôi):**
   * Bỏ 0.1s đầu và 0.2s cuối. 
   * Tính toán `duration = total_duration - 0.3`.
   * Video filter: `trim=start=0.1:duration=X,setpts=PTS-STARTPTS`.
   * *Lưu ý:* Phải áp dụng filter `atrim` trên các luồng âm thanh tương ứng để tránh lệch sync hình tiếng.
2. **CROP (Cắt lẹm viền):**
   * Zoom-in tương đương 2-3%.
   * Video filter: `crop=in_w*0.97:in_h*0.97`. 
   * Cần scale lại về độ phân giải gốc để khớp render: `scale=720:1280` (hoặc scale lại theo `in_w:in_h` ban đầu).
3. **EQ (Hiệu chỉnh Màu):**
   * Thay đổi thông số gốc một chút.
   * Video filter: `eq=contrast=1.02:brightness=-0.01:saturation=1.02`.

### Mẫu FFmpeg Filter Complex Tham Khảo:
```bash
[0:v]trim=start=0.1:duration={adjusted_dur},setpts=PTS-STARTPTS,crop=in_w*0.97:in_h*0.97,scale={width}:{height},eq=contrast=1.02:brightness=-0.01[v_mod];
[1:a]atrim=start=0.1:duration={adjusted_dur},asetpts=PTS-STARTPTS[a_voice_mod];
[2:a]atrim=start=0.1:duration={adjusted_dur},asetpts=PTS-STARTPTS[a_bgm_mod]...
```

### Triển khai
*   Viết lại logic tính toán tham số filter và chuỗi `-filter_complex` trong `assemble_final_video`.
*   Sử dụng `cv2` hoặc `ffprobe` để lấy `total_duration` thật của video gốc.
