# Video Creator Platform (Event-Driven)

Hệ thống quản lý điểm tập trung cho phép tạo nhiều loại video qua kiến trúc Plugin và Job Queue (Redis + Celery).

## 1. Yêu cầu (Prerequisites)
- Docker & Docker Compose

## 2. Khởi chạy Hệ thống toàn diện bằng Docker

```bash
cd video-creator-platform

# Khởi chạy tất cả: DB, Redis, API, Worker (Lần đầu sẽ tốn xíu thời gian build ảnh vì các thư viện AI nặng)
docker-compose up -d --build
```

**Các dịch vụ sẽ tự động chạy:**
- **API Server (Trang Quản trị)**: Chạy trên port `8000`.
- **Worker Node (Celery)**: Chạy ngầm, tự động kết nối Redis và lấy Job giải quyết.
- **Database (PostgreSQL)**: Port `5432`, volume gắn ngoài.
- **Redis (Message Broker)**: Port `6379`.

## 3. Xem Log hệ thống

Nếu bạn muốn theo dõi worker đang chạy render tới đâu:
```bash
docker-compose logs -f worker
```


## 4. Test Demo tạo luồng qua API
Bạn có thể mở giao diện Swagger UI tại: [http://localhost:8000/docs](http://localhost:8000/docs)

**Cách tạo Video Review:**
Gửi `POST /api/jobs`
```json
{
  "job_type": "review",
  "config_data": {
    "metadata": { "project_id": "demo_review" },
    "assets": {
      "logo": { "width": 160, "x": 48, "y": 160, "opacity": 0.9 },
      "audio": { "voiceover_path": "raw/voice.mp3", "voiceover_script": "raw/voice.txt" },
      "video_folders": { "01_hook": "raw/1/" }
    },
    "timeline_script": [
      {
        "segment": "01_hook",
        "time_range": [0.0, 5.0],
        "video_source": "01_hook"
      }
    ],
    "render_settings": {
      "resolution": [1080, 1920],
      "auto_subtitle": false
    }
  }
}
```

Xem trạng thái video tại: `GET /api/jobs/{id}`. Trạng thái sẽ tự chuyển từ `PENDING` -> `PROCESSING` -> `SUCCESS`.
