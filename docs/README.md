# Video Creator Platform

Hệ thống quản lý điểm tập trung cho phép tạo nhiều loại video qua kiến trúc Plugin và Job Queue (Redis + Celery). Dành cho các Content Creator, Marketer muốn tự động hóa quá trình dựng video ngắn (TikTok, Shorts, Reels).

Toàn bộ tài liệu hệ thống được đặt tại thư mục `docs/`.

## 📚 Mục Lục Tài Liệu

1. **[Tổng Quan & Cài Đặt (Quickstart)](./README.md)** - Đọc tài liệu này trước!
2. **[Kiến Trúc Hệ Thống](./ARCHITECTURE.md)** - Gồm sơ đồ hệ thống, luồng công việc, cơ sở dữ liệu.
3. **[Hướng Dẫn Dành Cho Developer](./DEVELOPMENT_GUIDE.md)** - Thiết lập môi trường local host, E2E testing, và viết Plugin mới.
4. **[Tài Liệu Cấu Trúc API (Admin API)](./API_REFERENCE.md)** - Đặc tả các router Auth, Projects, Folders, Assets, Jobs, Chat SSE, Translify, Downloads, và Worker-Config.
5. **[Hướng Dẫn: Plugin Video Review](./WORKER_REVIEW.md)** - Phù hợp tạo video Kể Chuyện, Đạt Tỉ Lệ Giữ Chân Cao (Retention B-Roll).
6. **[Hướng Dẫn: Plugin Video Unbox](./WORKER_UNBOX.md)** - Hỗ trợ cả 2 chế độ: Basic Unbox (Music sync beat-drop) và Viral Unbox (YOLO Smart Crop & Speed Ramping).
7. **[Bộ Tài Liệu Doanh Nghiệp: Plugin Video Translify](./translify/1_EXECUTIVE_SUMMARY.md)** - *[TIÊN PHONG SOTA]* Quy trình bản địa hóa video Douyin/Kuaishou và inpainting xóa chữ, bao gồm:
   - 🏢 **[Tóm Tắt Doanh Nghiệp](./translify/1_EXECUTIVE_SUMMARY.md)**: Bài toán kinh doanh, chống Reup và hiệu quả ROI.
   - 🏗️ **[Kiến Trúc Hệ Thống](./translify/2_SYSTEM_ARCHITECTURE.md)**: Thiết kế 2-Stage bất đồng bộ và Video-as-Data Schema.
   - ⚙️ **[Luồng Xử Lý Chi Tiết](./translify/3_PIPELINE_FLOW.md)**: Kỹ thuật 5 Phase đầu cuối, Lucas-Kanade tracking & Inpaint.
   - 🔬 **[Hồ Sơ Công Nghệ](./translify/4_TECHNOLOGY_STACK.md)**: Thông số và phân bổ GPU của các SOTA AI Models (MDX-Net, Whisper, ProPainter, Qwen).
   - 🛠️ **[Sổ Tay Vận Hành & DevOps](./translify/5_OPERATIONS_TROUBLESHOOTING.md)**: Hướng dẫn cài đặt local, VRAM safety, Monkeypatches và tra cứu lỗi nhanh.
   - *(Tham khảo tài liệu hướng dẫn nhanh cũ: [WORKER_TRANSLIFY.md](./WORKER_TRANSLIFY.md))*
8. **[Hướng Dẫn: Worker TTS](./WORKER_TTS.md)** - *[NEW]* Quy trình sinh giọng thuyết minh tự động qua MeloTTS và Edge-TTS HoaiMy/NamMinh.

9. **[Hướng Dẫn: Worker Text2Img](./WORKER_TEXT2IMG.md)** - Thiết kế sinh ảnh nghệ thuật độc lập qua ComfyUI FLUX GPU API.
10. **[Tài Liệu: Kiến Trúc Chat Assistant](./WORKER_CHAT_STORAGE.md)** - Cơ chế lưu trữ dữ liệu chat và truyền nhận dữ liệu thời gian thực qua Stream Server-Sent Events (SSE).
11. **[Kiến Trúc: AI Leader Agent & Webhook TMCP](./tmcp_integration_leader_agent.md)** - Bộ định tuyến tổng đạo diễn AI, tự sửa lỗi tham số (Self-Healing) và tiếp nhận webhook.
12. **[Báo Cáo: Đánh Giá Database Audit](./DATABASE_AUDIT_REPORT.md)** - Phân tích, chuẩn hóa và tối ưu hóa cơ sở dữ liệu PostgreSQL.
13. **[Báo Cáo: Cấu Trúc Thư Mục & MinIO Storage Audit](./FOLDER_ARCHITECTURE_AUDIT.md)** - Bản đồ tương thích thư mục CapCut-style và Hard Delete.
14. **[Bản Thiết Kế: Nâng Cấp UI/UX Giao Diện Admin](./UI_UX_UPGRADES.md)** - Cải tiến bố cục sidebar, khu vực quản lý workers và nâng cao trải nghiệm người dùng.

---

## 🚀 Quickstart (Khởi Chạy Nhanh Local)

Hệ thống được thiết kế để chạy **cực kỳ tối ưu trên máy local (Host Machine)** thông qua các bộ shell scripts, không sử dụng Docker cho các container Python/Node để đảm bảo hiệu năng GPU (CUDA) tối đa cho AI Models và dễ dàng debug trực tiếp.

### 1. Yêu cầu Hệ thống (Prerequisites)
- Linux / WSL2 (Ubuntu 20.04 hoặc 22.04) đã cài đặt GPU Drivers (nếu cần render deep learning).
- Docker & Docker Compose (chỉ dùng để chạy hạ tầng nền).
- Python 3.10+ và Node.js 18+.

### 2. Khởi Chạy Toàn Bộ Hệ Thống

Để khởi chạy tất cả hạ tầng (DB, Redis, MinIO) trong Docker và tự động cài đặt venvs, khởi động Admin API, 12 Celery Workers, và React Frontend trên host:

```bash
cd marketing-video-agent

# Chạy script khởi động toàn bộ
./dev.sh
```

### 3. Khởi Chạy Tiết Kiệm Tài Nguyên (Selective Workers)

Nếu máy tính cá nhân của bạn bị giới hạn RAM/CPU, bạn không nên chạy cùng lúc cả 12 workers. Hãy sử dụng script chạy chọn lọc. Script này sẽ tự động đọc cấu hình trong database (`WorkerConfig` table) và chỉ khởi chạy các worker được đánh dấu **`is_enabled = True`**:

```bash
cd marketing-video-agent

# Khởi chạy hạ tầng và chỉ bật các workers được enable trên Web Admin UI
./dev-selective.sh
```

### 4. Dừng Toàn Bộ Hệ Thống

Khi làm việc xong hoặc muốn khởi động lại sạch sẽ, hãy chạy script sau để dừng triệt để các tiến trình chạy ngầm (API, Celery workers, Vite frontend) và hạ container Docker:

```bash
cd marketing-video-agent

# Tắt và dọn dẹp sạch sẽ tài nguyên
./dev-stop.sh
```

---

## 🖥️ Các Cổng Dịch Vụ Mặc Định (Port Mappings)

Khi hệ thống khởi chạy thành công qua `./dev.sh` hoặc `./dev-selective.sh`:
* **Frontend Admin**: `http://localhost:9173` (Giao diện quản trị, xem danh mục, chat, tạo video)
* **Admin API (Swagger UI)**: `http://localhost:9100/docs` (FastAPI Swagger Docs)
* **Database (PostgreSQL)**: `localhost:5432` (Username: `admin`, Password: `password123`, DB: `video_creator`)
* **Redis Broker**: `localhost:6379`
* **MinIO Object Storage Console**: `http://localhost:9001` (Username: `minioadmin`, Password: `minioadmin`)
* **MinIO API Port**: `http://localhost:9000` (Endpoint dùng cho S3 upload)

