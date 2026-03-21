# Admin API Reference

Hệ thống quản lý Video Platform được cung cấp một Admin API xây dựng bằng FastAPI, hỗ trợ đầy đủ các module xác thực (JWT) và quản lý tiến trình.

## 1. Xác Thực (Authentication)

- Sừ dụng chuẩn `Bearer Token (JWT)` với thuật toán `HS256`. 
- Tài khoản đăng nhập xử lý qua JWT payload expiration (Cấu hình mặc định 7 ngày).
- Tất cả request bảo mật yêu cầu gắn header:
  `Authorization: Bearer <token_chuoi_nhan_dc_khi_login>`

## 2. API Endpoints Chính

Swagger UI Documents trực quan: `http://localhost:8000/docs` 

### 🟢 Router `Auth` (`/api/auth`)
- `POST /api/auth/register`: Đăng ký tài khoản hệ thống (yêu cầu Password độ dài tối thiểu 6 ký tự).
- `POST /api/auth/login`: Xác minh mật khẩu Hash (Bcrypt), khởi tạo chuỗi JW Token.
- `GET /api/auth/me`: Trả về thông tin User Profile hiện tại.

### 🟢 Router `Projects` (`/api/projects`)
- `POST /api/projects`: Tạo thư mục quản lý dự án (Project).
- `GET /api/projects`: Liệt kê tất cả dự案 (của User đang login).
- `DELETE /api/projects/{id}`: Xóa dự án (Cơ chế Delete CASCADE sẽ kéo theo tự hủy tất cả Jobs và Logs con).

### 🟢 Router `Assets` (`/api/assets`)
Quản lý File tài nguyên thô (Ảnh, MP4 clip sảnh, MP3) được lưu trên hệ MinIO S3.
- `POST /api/assets/upload`: Gửi File Multipart, Tool tự động upload lên MinIO backend bucket và lưu Record vào AssetDB.
- `GET /api/assets`: Chức năng hiển thị danh mục files của dự án.
- `DELETE /api/assets/{id}`: Soft delete Database record và Best-effort wipe từ S3 MinIO.

### 🟢 Router `Jobs` (`/api/jobs`)
Nơi ra lệnh gọi Worker Node thực hiện dựng Video.
- `POST /api/jobs`: Khởi tạo Pipeline dựng video theo type (`review`, `unbox`), chuyển Task vào Celery Queue tương ứng. Trạng thái khởi điểm `PENDING`.
- `GET /api/jobs`: Danh sách cấu hình JSON Job đang xử lý / đã hoàn thành.
- `GET /api/jobs/{id}`: Giám sát Trạng thái & % Process liên tục (Dùng để Frontend làm thanh Loading Bar).
- `GET /api/jobs/{id}/download`: Tạo **S3 Presigned URL** sử dụng trong 2 tiếng cho phép người dùng download MP4 trực tiếp về máy an toàn (mà không phải expose root domain file_storage).

### 🟢 Router `System` (`/api/`)
- `GET /api/health`: Kiểm tra node alive.
- `GET /api/workers`: Thống kê các Worker Node hiện hữu, `last_heartbeat` cập nhật Node online.
- `GET /api/templates`: Danh sách kịch bản mẫu cấu hình dựng hình.

## 3. Cấu hình Env
API thiết lập qua `shared_core/config.py`. Tham số tham chiếu Env: `DATABASE_URL`, `REDIS_URL`, `MINIO_*`, `JWT_SECRET_KEY`...
