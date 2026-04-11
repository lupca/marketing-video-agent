# Video Creator Platform

Hệ thống quản lý điểm tập trung cho phép tạo nhiều loại video qua kiến trúc Plugin và Job Queue (Redis + Celery). Dành cho các Content Creator, Marketer muốn tự động hóa quá trình dựng video ngắn (TikTok, Shorts, Reels).

Toàn bộ tài liệu hệ thống được đặt tại thư mục `docs/`.

## 📚 Mục Lục Tài Liệu

1. [Tổng Quan & Cài Đặt (Quickstart)](./README.md) - Đọc file này trước!
2. [Kiến Trúc Hệ Thống](./ARCHITECTURE.md) - Gồm sơ đồ hệ thống, luồng công việc, database
3. [Hướng Dẫn Dành Cho Developer](./DEVELOPMENT_GUIDE.md) - Unit Tests, E2E, chạy Local
4. [Tài Liệu Cấu Trúc API (Admin API)](./API_REFERENCE.md) - Auth, Projects, Jobs, Assets
5. [Hướng Dẫn: Plugin Video Review](./WORKER_REVIEW.md) - Phù hợp tạo video Kể Chuyện, Đập hộp có Voiceover
6. [Hướng Dẫn: Plugin Video Unbox](./WORKER_UNBOX.md) - Phù hợp tạo video ghép nhiều đoạn nhạc (Beat-drop sync)

---

## 🚀 Quickstart (Chạy Nhanh)

### 1. Yêu cầu (Prerequisites)
- Docker & Docker Compose
- Hệ thống có khả năng kết nối mạng tải model AI lần đầu

### 2. Khởi chạy với Docker

```bash
cd video-creator-platform

# Khởi chạy tất cả: DB, Redis, API, Worker (Review + Unbox), Frontend
docker-compose up -d --build
```

**Các dịch vụ sẽ chạy tại local:**
- **Frontend Admin**: `http://localhost:5173`
- **Admin API (Swagger UI)**: `http://localhost:8000/docs`
- **Database (PostgreSQL)**: Port ``
- **Redis (Message Broker)**: Port `6379`
- **MinIO (Storage)**: `http://localhost:9001` (Admin port) / `http://localhost:9000` (API)
- **Celery Workers**: Chạy ngầm trong container `worker-review` và `worker-unbox`

### 3. Xem Log worker

Lệnh theo dõi tiến độ render video từ các Worker:
```bash
docker-compose logs -f worker-review worker-unbox
```

### 4. Tắt hệ thống

```bash
docker-compose down
```
