# Hướng Dẫn Dành Cho Developer

Tài liệu phục vụ quy trình làm việc phát triển local, kiểm thử và thiết lập cho Team Developer tham gia bảo trì, thêm Plugin hệ thống `video-creator-platform`.

## 1. Thiết lập Môi trường Local (Không dùng Docker)

Dành cho Developers cần Debug trực tiếp bằng Breakpoint qua IDE. Shell script `dev.sh` hỗ trợ tải Infra DB mà không ẩn mất StdOut lỗi Python:

```bash
# Setup cài đặt 3 virtual env rỗng dành cho API, Celeries:
python3 -m venv .venv-api
python3 -m venv worker_review/.venv
python3 -m venv worker_unbox/.venv

# Kích hoạt Local Script
./dev.sh
```
`dev.sh` sẽ gọi `docker-compose up -d db redis minio` để chạy Infrastructure, tiếp theo nó sẽ cài Dependencies tự động (nếu thiếu) và kích hoạt song song API (port 8000), 2 Celery Workers và Frontend. 

Để tắt toàn bộ tiến trình:
```bash
# Tắt script
[Ctrl + C] 
# Dọn dẹp process mồ côi
pkill -f uvicorn
pkill -f celery
pkill -f vite
```

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

Hệ thống hoạt động như một cỗ máy đa "phích cắm". Nếu Content yêu cầu loại video thứ 3 (VD: `video_podcast`), quy trình là:
1. Tạo Folder: `worker_podcast/`
2. Define thuật toán Python riêng sinh ra MP4 (VD: `podcast_builder.py`).
3. Tạo `celery_worker.py` import `worker_base` từ `shared_core`:

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
4. Define Queue Mapping lại vào phần Route `celery_client.py` bên Admin API Backend:
   `"worker_podcast.tasks.*": {"queue": "podcast_queue"}`
5. Bổ sung Service Task vào `docker-compose.yml` để Orchestration! Hoàn tất.
