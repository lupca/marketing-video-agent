# Kế hoạch Nâng Cấp Asset Library (PostgreSQL & FastAPI)

**Mục tiêu:** Tối ưu hóa cấu trúc quản lý file của `marketing-video-agent` tương tự như các phần mềm làm phim chuyên nghiệp (Premiere, CapCut). Mỗi video sẽ được quản lý dưới dạng một thư mục dự án, chứa toàn bộ tài nguyên đầu vào, file trung gian và một thư mục con `output` chứa video thành phẩm.

---

## 1. Các Trọng Tâm Thiết Kế Mới

### 1.1. Cơ chế Hard Delete (Xóa triệt để)
* **Nguyên tắc:** Dữ liệu trên Database và file vật lý trên ổ cứng (MinIO) phải đồng bộ.
* **Cách hoạt động:** 
  1. Khi người dùng yêu cầu xóa tệp tin (`Asset`) hoặc thư mục (`MediaFolder`).
  2. Hệ thống tìm kiếm các bản ghi liên quan trong PostgreSQL.
  3. Lấy ra tất cả đường dẫn S3 (`s3_url`).
  4. Gọi lệnh `delete_object` tới MinIO cho từng file để giải phóng hoàn toàn dung lượng ổ cứng.
  5. Xóa các bản ghi tương ứng trong database (bảng `assets` và `media_folders`). Đối với thư mục, áp dụng xóa đệ quy (Cascade Delete).

### 1.2. Gom Tài Nguyên theo Thư Mục Video (Project-based Directory)
* **Cấu trúc:** Mỗi video (hoặc Job) khi được tạo sẽ tự động có một thư mục cha đại diện mang tên trùng với tên Video/Job (ví dụ: `Video_Giáng_Sinh_2026`).
* **Quản lý file:**
  - **Tài nguyên đầu vào & File trung gian:** Ảnh gốc, nhạc nền MP3, kịch bản văn bản (Text), voice timeline (.mp3/.wav từ TTS) đều được lưu trực tiếp tại thư mục cha `Video_Giáng_Sinh_2026/`.
  - **Thư mục con Output:** Tự động tạo thư mục con tên là `output` nằm bên trong thư mục cha (`Video_Giáng_Sinh_2026/output/`). Mọi video render thành phẩm sẽ được lưu tại đây. Khi edit hoặc xuất lại, các file video mới cũng sẽ nằm tại thư mục `output` này.
* **Đường dẫn MinIO:** 
  - Thư mục dự án: `jobs/{job_id}_{video_name}/`
  - Thư mục output: `jobs/{job_id}_{video_name}/output/`

---

## 2. Đánh Giá Ảnh Hưởng & Giải Pháp Cho Tính Năng "Copy Job"

### 2.1. Phân Tích Cơ Chế Sao Chép
* Tính năng "Copy/Clone Job" hiện tại đang chạy ở **Frontend**:
  1. Gửi request `GET /api/jobs/{old_job_id}` để lấy config của Job cũ.
  2. Điền dữ liệu vào form tạo Job mới trên màn hình (cho phép chỉnh sửa).
  3. Gửi request `POST /api/jobs` để tạo một Job mới với một ID mới (ví dụ: `Job 124`).

### 2.2. Phương Án Xử Lý Để Tránh Xung Đột
Để đảm bảo Job mới được tạo độc lập hoàn toàn và không ghi đè lên dữ liệu của Job cũ:
1. **Tạo thư mục mới độc lập:** Khi Job mới được submit tạo thành công, Backend sẽ tự động sinh một thư mục `MediaFolder` mới trên Database đại diện cho Video mới này (ví dụ: `Video_Giáng_Sinh_2026_Copy`).
2. **Tham chiếu Assets đầu vào (User-uploaded):** Các assets gốc do user tải lên ban đầu (ảnh, nhạc gốc) sẽ được giữ nguyên liên kết tham chiếu (Reference) thông qua bảng trung gian `JobAsset`. Điều này giúp tiết kiệm dung lượng ổ cứng vì không cần nhân bản các file thô cực lớn.
3. **Sinh mới file trung gian và output:** Khi Worker xử lý Job mới, nó sẽ tự động tạo một thư mục con `output` mới tương ứng với thư mục dự án mới. Tất cả các file trung gian (giọng đọc TTS mới, timeline mới) và video xuất ra sẽ được lưu độc lập tại đây. 
4. **Kết quả:** Người dùng có 2 thư mục dự án riêng biệt trên giao diện, mỗi bên tự quản lý file output và file nháp của mình mà không lo sợ bị ghi đè chéo.

---

  - Tạo model `MediaFolder` hỗ trợ cây thư mục (`parent_id`).
  - Thêm cột `folder_id` và `display_name` vào bảng `Asset`.
  - Liên kết bảng `VideoJob` với `MediaFolder` thông qua `folder_id`.
  - Viết CRUD APIs cho `/api/folders`.
  - Cập nhật `/api/assets/upload` để hỗ trợ upload trực tiếp vào thư mục chỉ định.
  - Viết API di chuyển file (`PUT /api/assets/{id}`).
  - Tích hợp cơ chế **Hard Delete** trong API xóa File/Folder (xóa vật lý trên MinIO trước khi xóa DB).
  - Khi worker khởi chạy, tạo thư mục dự án trên DB và MinIO theo mẫu `jobs/{job_id}_{video_name}/`.
  - Cập nhật các worker con (Text2Img, Review, Unbox, Translify) để lưu các file nháp/trung gian (TTS, script) vào thư mục này.
  - Khi xuất video, tạo thư mục con `output` và lưu video thành phẩm vào `jobs/{job_id}_{video_name}/output/`.
  - Đồng bộ tự động các file này thành các bản ghi `Asset` trong database.
  - Đảm bảo khi nhân bản Job, hệ thống tự động ánh xạ và tạo cây thư mục mới, giữ nguyên tính độc lập của video mới.
