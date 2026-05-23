# Phân Tích & Thiết Kế Hệ Thống: Worker Text-to-Image (ComfyUI FLUX)

Tài liệu này mô tả thiết kế kiến trúc và các bước triển khai cho một worker mới chuyên đảm nhiệm việc tạo ảnh (Text-to-Image) bằng mô hình FLUX thông qua ComfyUI API. Kết quả đầu ra sẽ được lưu trữ tự động lên MinIO, đồng nhất với kiến trúc của các worker video hiện tại.

## 1. Tổng Quan Kiến Trúc (Architecture Overview)

Dựa trên kiến trúc Event-Driven của hệ thống hiện tại, chúng ta sẽ xây dựng **Worker Text2Img** hoạt động theo mô hình Client-Server với ComfyUI:

1. **ComfyUI Server (Local)**: Đóng vai trò là GPU Backend Service. Chạy độc lập trên máy chủ local (cổng `8188`), đã load sẵn workflow FLUX.
2. **Worker Text2Img (Celery Node)**: Đóng vai trò là Orchestrator. Nó lắng nghe Queue, nhận Job, gửi request đến ComfyUI, chờ kết quả, và upload file ảnh đầu ra lên MinIO.

**Luồng dữ liệu (Data Flow):**
`Frontend UI` -> `Admin API` (Tạo Job PENDING) -> `Redis Queue (text2img_queue)` -> `Worker Text2Img` -> `ComfyUI API (Port 8188)` -> `Worker Text2Img` (Lấy file ảnh) -> `MinIO Storage` -> `Cập nhật DB (SUCCESS)`.

---

## 2. Thiết Kế Các Thành Phần (Component Design)

### A. Frontend Admin UI
- **Giao diện**: Thêm màn hình/chức năng "Image Generator".
- **Input**: `prompt` (văn bản miêu tả ảnh), `width`, `height`, `seed` (tuỳ chọn).
- **Hành vi**: Gửi POST request tạo Job mới với `job_type="text2img"`. Lắng nghe/polling trạng thái Job và hiển thị ảnh kết quả từ MinIO URL.

### B. Admin API Backend
- **Cập nhật Schema**: Bổ sung `text2img` vào danh sách `VALID_JOB_TYPES` trong `shared_core/schemas.py`.
- **Định tuyến Celery**: Thêm rule định tuyến vào `admin-api/celery_client.py` để đẩy các task của worker này vào `text2img_queue`.

### C. Worker Text2Img (Thành phần mới)
Tạo folder mới `worker_text2img/` ngang hàng với các worker khác, chứa:
1. **`celery_worker.py`**: Khai báo app Celery, lắng nghe hàng đợi `text2img_queue`.
2. **`engine.py`**: Chứa logic gọi HTTP API tới ComfyUI (dựa trên đoạn code tham khảo), đọc file ảnh trả về và sử dụng `shared_core.minio_utils` để upload.

### D. ComfyUI (GPU Backend)
- Server chạy sẵn ở `http://127.0.0.1:8188`.
- Cấu hình Workflow JSON: Định nghĩa sẵn pipeline cho model `flux1-schnell-fp8-e4m3fn.safetensors`.

---

## 3. Các Bước Triển Khai Cho Developer (Task Breakdown)

### Bước 1: Cập Nhật Shared Core & Admin API
1. Mở `shared_core/schemas.py`:
   ```python
   VALID_JOB_TYPES = {"review", "unbox", "unbox_viral", "slideshow", "promotion", "translify", "text2img"}
   ```
2. Mở `admin-api/celery_client.py`:
   ```python
   task_routes={
       # ... các queue cũ ...
       "worker_text2img.tasks.*": {"queue": "text2img_queue"},
   }
   ```

### Bước 2: Xây Dựng `worker_text2img`
1. Tạo thư mục `worker_text2img/` và copy các file cơ bản từ một worker có sẵn (như `requirements.txt`, `Dockerfile`).
2. Viết file kết nối ComfyUI và Upload MinIO (`engine.py`):
   - Chuyển đổi mã code `urllib.request` thành function gọi API.
   - Thêm bước đọc file ảnh từ thư mục output của ComfyUI (hoặc tải trực tiếp nếu API trả về base64/binary).
   - Tích hợp hàm MinIO:
     ```python
     from shared_core.minio_utils import MinioHandler
     # ...
     minio_handler = MinioHandler()
     object_name = f"projects/{project_id}/images/flux_{job_id}.png"
     url = minio_handler.upload_file(local_file_path, object_name)
     return url
     ```

3. Viết Task cho Celery (`celery_worker.py`):
   ```python
   import os
   from celery import Celery
   from shared_core.worker_base import BaseVideoWorker # hoặc tạo BaseImageWorker
   from .engine import generate_image_and_upload

   celery_app = Celery("worker_text2img", broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

   @celery_app.task(name="worker_text2img.tasks.generate_image", bind=True)
   def process_image_job(self, job_id: int, payload: dict):
       # 1. Khởi tạo worker logic để cập nhật DB (Status = PROCESSING)
       # 2. Gọi engine
       prompt = payload.get("config_data", {}).get("prompt", "")
       project_id = payload.get("project_id", "default")
       
       result_url = generate_image_and_upload(prompt, job_id, project_id)
       
       # 3. Cập nhật DB (Status = SUCCESS, result_url = result_url)
       return {"status": "success", "url": result_url}
   ```

### Bước 3: Triển Khai & Testing
1. Cập nhật `docker-compose.yml` (nếu chạy Docker) hoặc file chạy `dev.sh` để khởi động thêm node `worker_text2img`.
   ```yaml
   worker_text2img:
     build: ./worker_text2img
     command: celery -A celery_worker worker -Q text2img_queue --loglevel=info
     # ... (env vars)
   ```
2. Lưu ý về Network: Vì ComfyUI chạy ở `127.0.0.1:8188` trên Host (hoặc WSL), nếu worker chạy trong Docker, cần trỏ API endpoint về `host.docker.internal:8188` thay vì `127.0.0.1`.

### Bước 4: Tích Hợp Frontend
- Tạo UI gửi request.
- Parse `config_data` thành JSON có cấu trúc `{"prompt": "Giá trị từ form", "width": 1024, "height": 1024}`.
- Hiển thị ảnh sau khi hệ thống trả về SUCCESS.

---

## 4. Xử Lý Lỗi (Error Handling)
- **ComfyUI Disconnected**: Nếu worker không gọi được port 8188, cập nhật Job Status thành `FAILED` với log: *"Không thể kết nối ComfyUI Server"*.
- **Timeout**: Sinh ảnh FLUX có thể mất thời gian, cần setup timeout hợp lý cho Celery Task và `urllib.request`.
- **Dọn dẹp (Cleanup)**: Xóa ảnh local trong folder output của ComfyUI (hoặc `/tmp` của worker) sau khi upload MinIO thành công để tránh đầy ổ cứng.