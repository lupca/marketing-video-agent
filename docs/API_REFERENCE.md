# Admin API Reference

Hệ thống quản lý Video Platform được cung cấp một Admin API xây dựng bằng FastAPI, hỗ trợ đầy đủ các module xác thực (JWT) và quản lý tiến trình.

## 1. Xác Thực (Authentication)

- Sừ dụng chuẩn `Bearer Token (JWT)` với thuật toán `HS256`. 
- Tài khoản đăng nhập xử lý qua JWT payload expiration (Cấu hình mặc định 7 ngày).
- Tất cả request bảo mật yêu cầu gắn header:
  `Authorization: Bearer <token_chuoi_nhan_dc_khi_login>`

## 2. API Endpoints Chính

## 2. API Endpoints Chính

Swagger UI Documents trực quan: `http://localhost:9100/docs` 

### 🟢 Router `Auth` (`/api/auth`)
Quản lý người dùng, đăng ký và xác thực JWT.
- `POST /api/auth/register`: Đăng ký tài khoản hệ thống (yêu cầu Password độ dài tối thiểu 6 ký tự).
- `POST /api/auth/login`: Xác minh mật khẩu Hash (Bcrypt), khởi tạo chuỗi JW Token.
- `GET /api/auth/me`: Trả về thông tin User Profile hiện tại.

### 🟢 Router `Projects` (`/api/projects`)
Quản lý các Dự án của người dùng.
- `POST /api/projects`: Tạo dự án (Project) mới.
- `GET /api/projects`: Liệt kê tất cả dự án của người dùng đang đăng nhập.
- `DELETE /api/projects/{id}`: Xóa dự án (Cơ chế Cascade sẽ kéo theo tự hủy tất cả Folders, Assets, Jobs, và Logs con).

### 🟢 Router `Folders` (`/api/folders`)
Quản lý cấu trúc cây thư mục tài nguyên dự án (CapCut/Premiere-style directory tree).
- `POST /api/folders`: Tạo thư mục con trong dự án (hỗ trợ thư mục lồng nhau `parent_id`).
- `GET /api/folders`: Lấy danh sách tất cả các thư mục của dự án.
- `GET /api/folders/{id}`: Xem thông tin chi tiết của một thư mục cụ thể.
- `PUT /api/folders/{id}`: Đổi tên hoặc di chuyển thư mục cha (hỗ trợ kiểm tra cyclic redundancy).
- `DELETE /api/folders/{id}`: Thực hiện **Xóa đệ quy triệt để (Recursive Hard Delete)** toàn bộ thư mục con, xóa vĩnh viễn tệp vật lý tương ứng trên MinIO S3, và dọn dẹp DB Asset records.

### 🟢 Router `Assets` (`/api/assets`)
Quản lý File tài nguyên thô (Ảnh, MP4 clip sảnh, MP3) được lưu trên hệ MinIO S3.
- `POST /api/assets/upload`: Gửi File Multipart, Tool tự động upload lên MinIO backend bucket và lưu Record vào bảng `assets`.
- `GET /api/assets`: Chức năng hiển thị danh mục files của dự án/thư mục.
- `DELETE /api/assets/{id}`: Hard delete - Xóa record khỏi database và giải phóng dung lượng bằng lệnh xóa vật lý tệp trên MinIO S3.

### 🟢 Router `Jobs` (`/api/jobs`)
Nơi ra lệnh gọi các Celery Worker thực hiện dựng Video.
- `POST /api/jobs`: Khởi tạo Pipeline dựng video theo type (`review`, `unbox`, `slideshow`, `promotion`, `translify`), chuyển Task vào Celery Queue tương ứng. Trạng thái khởi điểm `PENDING`.
- `GET /api/jobs`: Danh sách cấu hình JSON Job đang xử lý / đã hoàn thành.
- `GET /api/jobs/{id}`: Giám sát Trạng thái & % Process liên tục (Dùng để Frontend làm thanh Loading Bar).
- `GET /api/jobs/{id}/download`: Tạo **S3 Presigned URL** sử dụng trong 2 tiếng cho phép người dùng download MP4 trực tiếp về máy an toàn (mà không phải expose root domain file_storage).

### 🟢 Router `Chat Assistant` (`/api/chat`)
Trợ lý AI hỗ trợ sáng tạo kịch bản và prompt tích hợp, truyền dữ liệu thời gian thực.
- `POST /api/chat/sessions`: Tạo một phiên hội thoại chat mới liên kết với Project.
- `GET /api/chat/sessions`: Lấy danh sách các phiên hội thoại trong một Project.
- `GET /api/chat/sessions/{session_id}/messages`: Lấy toàn bộ lịch sử tin nhắn của một phiên hội thoại (tối đa 10 tin nhắn gần nhất làm context).
- `POST /api/chat/sessions/{session_id}/messages`: Gửi câu hỏi lên và nhận tin nhắn phản hồi dưới dạng **Stream Server-Sent Events (SSE)** từ Ollama/OpenAI, tự động lưu cả user và assistant messages vào DB.
- `PUT /api/chat/sessions/{session_id}`: Cập nhật tên cuộc hội thoại hoặc mô hình LLM đã chọn.
- `DELETE /api/chat/sessions/{session_id}`: Xóa phiên hội thoại và toàn bộ tin nhắn liên quan.

### 🟢 Router `Translify` (`/api/translify`)
Quản lý quy trình dịch thuật, Việt hóa video nước ngoài và xử lý inpainting xóa chữ Trung Quốc.
- `GET /api/translify/projects/{job_id}`: Lấy dữ liệu phân tích kịch bản chi tiết của dự án dịch thuật Douyin (gồm mảng text tiếng Trung, tiếng Việt nháp, vocals, BGM, và thời lượng).
- `PUT /api/translify/projects/{job_id}`: Cập nhật cấu hình dịch dự án (sửa text dịch, thay đổi BGM, chọn voice thuyết minh, tone giọng, kêu gọi hành động CTA).
- `POST /api/translify/projects/{job_id}/approve`: Duyệt kịch bản dịch và đẩy tác vụ render video (Stage 2) vào hàng đợi `translify_queue`.
- `POST /api/translify/projects/{job_id}/reopen`: Mở lại dự án về trạng thái chỉnh sửa (`WAITING_FOR_REVIEW`).
- `POST /api/translify/tools/rewrite`: Sử dụng LLM Ollama tự động dịch và viết lại câu thoại tiếng Việt theo đúng giới hạn thời lượng (Word-budget co giãn) và tone giọng mong muốn.

### 🟢 Router `Downloads` (`/api/downloads`)
Quản lý các tiến trình tải video mạng xã hội độc lập về MinIO S3 làm Asset.
- `POST /api/downloads`: Khởi tạo một job tải video (ví dụ: từ Douyin/Kuaishou/YouTube), đẩy vào hàng đợi `download_queue` của `worker_download`.
- `GET /api/downloads`: Danh sách các tiến trình tải về của người dùng.
- `GET /api/downloads/{job_id}`: Kiểm tra trạng thái và phần trăm tiến độ tải.
- `GET /api/downloads/{job_id}/logs`: Xem lịch sử log vết quá trình download (ví dụ: tải luồng yt-dlp, convert định dạng).
- `GET /api/downloads/{job_id}/download`: Tạo S3 Presigned URL để tải file download thành phẩm về máy.
- `DELETE /api/downloads/{job_id}`: Xóa record lịch sử download.

### 🟢 Router `Agents` (`/api/agent`)
Quản lý các phiên hoạt động của Đạo Diễn AI (Leader Agent) điều phối kịch bản tự động.
- `POST /api/agent/sessions`: Khởi tạo một phiên Đạo diễn AI dựa trên keyword và cấu hình yêu cầu, đẩy task vào hàng đợi `agent_queue`.
- `GET /api/agent/sessions`: Lấy danh sách các phiên chạy Agent của người dùng.
- `GET /api/agent/sessions/{session_id}`: Xem chi tiết trạng thái phiên chạy Agent.
- `GET /api/agent/sessions/{session_id}/logs`: Xem log chi tiết từng bước tư duy và hoạt động của Agent.
- `POST /api/agent/sessions/{session_id}/retry`: Thử lại phiên chạy Agent bị lỗi (dọn dẹp log cũ và đưa vào hàng đợi `agent_queue`).
- `POST /api/agent/sessions/{session_id}/cancel`: Hủy ngang phiên chạy Agent đang ở trạng thái PENDING hoặc RUNNING.

### 🟢 Router `System / Workers` (`/api/worker-config`)
Quản lý động trạng thái hoạt động của các tiến trình Worker Celery trên máy Host.
- `GET /api/worker-config`: Lấy tổng quan trạng thái, tổng số workers đang chạy, bật, hoặc tắt.
- `GET /api/worker-config/{worker_type}`: Xem cấu hình chi tiết của một loại worker.
- `PUT /api/worker-config/{worker_type}`: Cập nhật thông số vận hành của một worker.
- `POST /api/worker-config/{worker_type}/enable`: Bật worker. Thực hiện ghi DB và gọi spawner **khởi động trực tiếp tiến trình Celery trên máy Host**.
- `POST /api/worker-config/{worker_type}/disable`: Tắt worker. Thực hiện ghi DB và gọi spawner **dừng/kill tiến trình Celery tương ứng trên Host**.
- `POST /api/worker-config/batch/update`: Cập nhật bật/tắt hàng loạt nhiều workers cùng lúc dưới background task để tránh blocking API thread.

### 🟢 Router `System` (`/api/`)
Các chức năng hệ thống cơ bản.
- `GET /api/health`: Kiểm tra sức khỏe của API server (Node alive).
- `GET /api/workers`: Thống kê nhịp tim (heartbeat) hoạt động của các worker.
- `GET /api/templates`: Danh sách kịch bản mẫu cấu hình dựng hình.

## 3. Cấu hình Env
API thiết lập qua `shared_core/config.py`. Tham số tham chiếu Env cốt lõi:
- `DATABASE_URL`: Đường dẫn PostgreSQL (`postgresql://admin:password123@localhost:5432/video_creator`).
- `REDIS_URL`: Endpoint Redis Broker (`redis://localhost:6379/0`).
- `MINIO_ENDPOINT`: URL kết nối MinIO S3 Storage (`localhost:9000`).
- `MINIO_ACCESS_KEY` & `MINIO_SECRET_KEY`: Khóa bảo mật MinIO (`minioadmin`).
- `JWT_SECRET_KEY`: Khóa mã hóa sinh chuỗi JW Token xác thực.
- `OLLAMA_BASE_URL`: URL dịch vụ LLM cục bộ (`http://localhost:11434`).

