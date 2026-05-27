# Hướng Dẫn Vận Hành & Khắc Phục Sự Cố: Worker Translify (DevOps & Operations)

Tài liệu này cung cấp hướng dẫn DevOps chuyên sâu để thiết lập, tối ưu hóa hiệu năng, vận hành và xử lý các sự cố thực tế trong quá trình chạy động cơ **Worker Translify**.

---

## 1. Thiết Lập Môi Trường Hệ Thống (Host Machine / WSL2)

Động cơ yêu cầu môi trường tăng tốc đồ họa phần cứng **NVIDIA GPU (CUDA 11.8 hoặc 12.x)** để đạt hiệu năng inpainting SOTA.

### A. Cài đặt các thư viện hệ thống (Bắt buộc)
Trước khi cài đặt môi trường ảo Python, bắt buộc phải cài đặt các thư viện hệ thống xử lý đa phương tiện và âm thanh trên máy chủ Linux/WSL2:

```bash
# Cập nhật repository và cài đặt thư viện biên dịch âm thanh
sudo apt-get update && sudo apt-get install -y \
    ffmpeg \
    rubberband-cli \
    libsndfile1 \
    git
```

> [!IMPORTANT]
> **Thiếu `rubberband-cli`** sẽ khiến module co giãn tiếng thuyết minh (`pyrubberband`) báo lỗi crash tiến trình ngay lập tức. Hãy luôn xác nhận lệnh `rubberband -h` hoạt động trong console.

### B. Khởi chạy thử nghiệm cục bộ qua CLI (Developer Testing)
Để kiểm thử độc lập luồng xử lý video đầu cuối (E2E) trực tiếp bằng dòng lệnh mà không qua hàng đợi Celery:

```bash
# Kích hoạt môi trường ảo của API
source .venv-api/bin/activate

# Khởi chạy chạy CLI dịch thử video raw
PYTHONPATH=worker_translify python3 -m worker_translify \
    --input worker_translify/atrox_88_china.mp4 \
    --output worker_translify/output.mp4 \
    --work-dir worker_translify/translify_tmp
```

---

## 2. Các Kỹ Thuật Tối Ưu Hóa Hiệu Năng VRAM & RAM Hệ Thống

### A. Cơ chế cô lập tiến trình (Process Isolation) chống rò rỉ RAM
Do nạp liên tiếp nhiều mô hình AI cồng kềnh (MDX-Net, Whisper, Paddle, ProPainter) trong một luồng dài sẽ gây tích tụ bộ nhớ cache của Python, dẫn đến việc CPU RAM tích lũy vượt ngưỡng 16GB-32GB và bị nhân Linux kích hoạt trình dọn dẹp bộ nhớ (OOM Killer) giết chết tiến trình Celery.
- **Giải pháp trong Code:** Translify cô lập các tác vụ nặng thông qua việc gọi các file CLI độc lập làm tiến trình con (`subprocess.run`). 
- Khi tiến trình con hoàn tất và thoát, toàn bộ bộ nhớ RAM/VRAM của mô hình AI nạp trong tiến trình đó được hệ điều hành **thu hồi sạch sẽ 100%**.
- Các file CLI cô lập này bao gồm: `cli_separate_vocals.py`, `cli_transcribe_whisper.py`, `cli_paddle_ocr.py`, `cli_scene_inpaint.py`, `cli_clean_frames.py`.

### B. Tối ưu hóa bộ nhớ GPU (VRAM Cleanup)
Sau khi kết thúc mỗi phân cảnh (`Scene`), hệ thống chủ động gọi bộ dọn rác của Python và giải phóng CUDA cache để chuẩn bị VRAM trống cho phân cảnh tiếp theo:

```python
import gc
import torch

gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()
```

### C. Khống chế tải inpainting khi GPU thiếu VRAM
Nếu chạy trên card đồ họa VRAM thấp (ví dụ RTX 3060 6GB/8GB của laptop hoặc bị tranh chấp tài nguyên), hãy mở file cấu hình inpaint và giảm `chunk_size` xuống `20` hoặc `15` khung hình:
- Đường dẫn: `worker_translify/translify_engine/phase3_compose.py`
- Thay đổi: Giảm `chunk_size = 30` xuống `chunk_size = 20` và `overlap = 6`.

---

## 3. Các Bản Vá Lỗi Hệ Thống Đặc Biệt (System Monkeypatches)

Translify tích hợp sẵn hai bản vá động (Monkeypatch) ngay khi import module để xử lý các xung đột phiên bản phần cứng và lỗi logic thư viện gốc:

### A. Vá lỗi PyTorchCV BufferedSequencer index trimming
* **Vấn đề:** Khi chia nhỏ video thành các phân cảnh rất ngắn (dưới 30 frames), thư viện ProPainter (`BufferedSequencer`) cố gắng dọn dẹp bộ đệm bằng hàm `trim_buffer_to` dẫn tới tính toán chỉ mục âm và báo lỗi `AssertionError: assert (index.start >= 0)`.
* **Giải pháp Monkeypatch:** Vô hiệu hóa tính năng dọn dẹp thừa bằng cách gán hàm thành rỗng:
  ```python
  from pytorchcv.models.common.stream import BufferedSequencer
  BufferedSequencer.trim_buffer_to = lambda self, start: None
  ```

### B. Vá lỗi PaddlePaddle IR Optimization Segfaults
* **Vấn đề:** Khi chạy trên một số cấu hình Driver CUDA mới, bộ tối ưu hóa đồ thị trung gian (IR Optim) của PaddleOCR cố gắng fuses các lớp `fc` gây ra lỗi sập bộ nhớ vật lý hệ thống (Segmentation Fault - SIGSEGV) khiến cả Celery worker biến mất không dấu vết.
* **Giải pháp Monkeypatch:** Can thiệp trực tiếp vào cấu hình khởi tạo của Paddle Inference:
  ```python
  import paddle.inference as inference
  original_config_init = inference.Config.__init__
  def patched_config_init(self, *args, **kwargs):
      original_config_init(self, *args, **kwargs)
      self.switch_ir_optim(False) # Tắt hoàn toàn IR optimization
      self.delete_pass("fc_fuse_pass")
  inference.Config.__init__ = patched_config_init
  ```

---

## 4. Bảng Tra Cứu Khắc Phục Sự Cố Nhanh (Troubleshooting Manual)

| Triệu chứng lỗi | Nguyên nhân gốc rễ | Giải pháp xử lý |
| :--- | :--- | :--- |
| **`FileNotFoundError: [Errno 2] No such file or directory: 'rubberband'`** | Thiếu gói cài đặt `rubberband-cli` trên hệ thống máy chủ. | Chạy lệnh `sudo apt-get install rubberband-cli` để cài đặt. |
| **`RuntimeError: CUDA Out of Memory (OOM)`** | Độ phân giải video quá lớn (4K/2K) hoặc `chunk_size` inpaint quá cao. | Giảm `image_resize_ratio` xuống `0.3` hoặc giảm `chunk_size` xuống `20`. |
| **Phụ đề tiếng Việt bị tràn viền hoặc lệch khung dọc** | Khung hình dọc 9:16 bị áp sai kích thước PlayRes trong file ASS. | Kiểm tra `subtitle_utils.py` đảm bảo cấu hình `PlayResX: 720` và `PlayResY: 1280` được gán chính xác cho video dọc. |
| **`Failed to connect to Ollama: [Errno 111] Connection refused`** | Dịch vụ Ollama chưa được bật hoặc chạy sai cổng mặc định `11434`. | Khởi chạy dịch vụ Ollama bằng lệnh `ollama serve` và đảm bảo model `qwen2.5:7b` đã được tải (`ollama pull qwen2.5:7b`). |
| **Giọng thoại tiếng Việt bị méo pitch hoặc tua nhanh quá mức** | Tỷ lệ dịch từ quá dài so với thời lượng scene và Ollama rewrite thất bại. | Chỉnh sửa trực tiếp rút ngắn câu dịch trên giao diện Web UI trước khi nhấn nút Render Stage 2. |
| **Lỗi khởi tạo PaddleOCR đứng đơ kéo dài vài phút** | Thư viện cố tải mô hình nhận dạng REC từ máy chủ Baidu Trung Quốc nhưng bị nghẽn mạng. | Đảm bảo truyền tham số `rec=False` trong hàm khởi tạo PaddleOCR của render engine để kích hoạt chế độ **det-only**. |
