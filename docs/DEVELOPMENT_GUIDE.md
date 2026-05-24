# Hướng Dẫn Dành Cho Developer

Tài liệu phục vụ quy trình làm việc phát triển local, kiểm thử và thiết lập cho Team Developer tham gia bảo trì, thêm Plugin hệ thống `video-creator-platform`.

## 1. Thiết lập Môi trường Local (Không dùng Docker cho Dịch vụ)

Dành cho Developers cần Debug trực tiếp bằng Breakpoint qua IDE và theo dõi StdOut lỗi Python thời gian thực. Hệ thống hỗ trợ 3 bộ shell script cốt lõi để quản lý toàn bộ vòng đời ứng dụng trên máy Host:

### A. Khởi chạy Toàn Bộ Dịch vụ (`./dev.sh`)
Script này sẽ tự động khởi động các hạ tầng lưu trữ và cơ sở dữ liệu (`Postgres, Redis, MinIO`) thông qua Docker Compose, sau đó tự động tạo môi trường ảo Python (`venv`) cho Admin API và **tất cả 12 workers** nếu chưa tồn tại, tự động cài đặt dependencies (`pip install`) và kích hoạt chạy song song API (port 9100), 12 Celery Workers và Frontend React (port 9173).

```bash
# Chỉ cần phân quyền và chạy trực tiếp từ thư mục gốc dự án:
chmod +x dev.sh dev-selective.sh dev-stop.sh
./dev.sh
```

### B. Khởi chạy Chọn Lọc Worker (`./dev-selective.sh`)
Trong quá trình phát triển local, việc khởi động cùng lúc cả 12 workers có thể gây quá tải RAM và CPU của máy tính cá nhân. Script `./dev-selective.sh` giải quyết vấn đề này bằng cách:
1. Kết nối vào database PostgreSQL để đọc bảng cấu hình **`worker_configs`** (`WorkerConfig` model).
2. Chỉ khởi chạy các Celery worker có thuộc tính **`is_enabled = True`** trên Web Admin UI (hoặc DB).
3. Giảm tải đến **80% tài nguyên** phần cứng khi develop tính năng riêng lẻ.

```bash
# Khởi chạy hạ tầng và chỉ bật các workers đã được active
./dev-selective.sh
```

### C. Dừng và Dọn dẹp Tiến trình (`./dev-stop.sh`)
Để tránh tình trạng "tiến trình mồ côi" (zombie processes) chiếm dụng port mạng, hãy luôn sử dụng script dừng hệ thống để tự động quét `pkill` các tiến trình uvicorn, celery, và vite trên host, đồng thời đưa hạ tầng Docker Compose xuống:

```bash
# Tắt và dọn dẹp sạch sẽ
./dev-stop.sh
```

*Lưu ý về môi trường ảo (venv):*
- Thư mục venv của Admin API: `.venv-api/` (nằm ở thư mục gốc).
- Thư mục venv của từng worker: `worker_<name>/venv/` (nằm trực tiếp bên trong từng thư mục worker tương ứng). Do đó, khi cần chạy test hoặc debug thủ công cho một worker nào đó, hãy kích hoạt môi trường tương ứng: `source worker_<name>/venv/bin/activate`.

## 2. Viết Code và Testing (`pytest`)

Mã nguồn được thiết kế cho khả năng mô phỏng SQLite In-Memory Database + Mocked Redis chạy các Unit/Integration test bằng công cụ `pytest`. Điều này đảm bảo E2E Tests không phá hỏng Database thực tế.

- Thư mục test nằm trong: `/tests/`
- Chạy hệ thống Pytest Local (Bắt buộc gán PYTHONPATH cho Module Shared Core nhận diện API app):
```bash
cd video-creator-platform

PYTHONPATH=./:./admin-api:./tests .venv-api/bin/python -m pytest tests/ -v
```

Kiểm tra độ phủ bao test Code Coverage:
```bash
.venv-api/bin/python -m pytest --cov=shared_core --cov=admin-api tests/
```

## 3. Tạo Plugin Loại Video Mới

Hệ thống hoạt động như một cỗ máy đa "phích cắm" (Pluggable Architecture). Nếu Content yêu cầu loại video mới (VD: `video_podcast`), quy trình phát triển là:

1. **Tạo Folder mới**: `worker_podcast/` ngang hàng với các worker khác.
2. **Khai báo Thuật toán**: Định nghĩa thuật toán Python riêng sinh ra MP4 (VD: `podcast_builder.py`).
3. **Tạo `celery_worker.py`**: Kế thừa và import `worker_base` từ `shared_core`:
   ```python
   from shared_core.worker_base import create_celery_app, execute_video_task

   celery_app = create_celery_app("worker_podcast")

   @celery_app.task(name="worker_podcast.tasks.process_video", bind=True)
   def process_video(self, job_id, config_data):
       execute_video_task(
           job_id=job_id,
           config_data=config_data,
           job_type="podcast",
           prepare_fn=download_s3_helper,
           build_fn=build_podcast_mp4
       )
   ```
4. **Định tuyến Hàng đợi (Queue Mapping)**: Bổ sung mapping lại vào phần Route `celery_client.py` bên Admin API Backend:
   `"worker_podcast.tasks.*": {"queue": "podcast_queue"}`
5. **Khai báo API Schemas**: Cập nhật `VALID_JOB_TYPES` trong `shared_core/schemas.py` để API chấp nhận loại job mới.
6. **Đăng ký vào Vòng đời Khởi chạy Local**:
   - Mở file `dev.sh`: Bổ sung đoạn code setup venv cho `worker_podcast` và lệnh khởi chạy Celery worker ở hàng đợi `podcast_queue`.
   - Mở file `dev-selective.sh`: Bổ sung logic khởi chạy Celery worker tương tự.
   - Thêm bản ghi khởi tạo mặc định trong `init_worker_configs.py` để hệ thống tự động chèn vào bảng quản trị `worker_configs`.
7. **Bổ sung Service Task vào `docker-compose.yml`**: Khai báo container tương ứng để chuẩn bị cho quá trình đóng gói deploy production lên máy chủ Staging/Production! Hoàn tất.
