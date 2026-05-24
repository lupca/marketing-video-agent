# Báo cáo Phân Tích Kiến Trúc Thư Mục & Đánh Giá Tác Động Lưu Trữ (Folder Architecture & Storage Audit Report)

**Tác giả:** Kỹ sư Kiến trúc Hệ thống & Kỹ sư Dữ liệu (System Architect & Data Engineer)  
**Mục tiêu:** Đánh giá tính tương thích của việc tách biệt các tác vụ Chat, TTS, và Sinh ảnh (Text2Img) ra khỏi `video_jobs` đối với cấu trúc thư mục dự án (Project-based Directory) trên PostgreSQL và Object Storage (MinIO). Đồng thời, phân tích các ảnh hưởng tiềm tàng tới toàn bộ hệ thống và đưa ra giải pháp giảm thiểu rủi ro (Mitigation).

*(Lưu ý: Theo yêu cầu trong phạm vi điều chỉnh mới, tài liệu này hoàn toàn loại bỏ thực thể `research_reports` và tập trung tối đa vào cấu trúc tệp tin, MinIO, DB, Chat, TTS và sinh ảnh).*

---

## 1. Bản Đồ Tương Thích: Cấu Trúc Thư Mục (DB & MinIO)

Dựa trên tài liệu đặc tả nâng cấp thư mục dự án (`docs/assest-feature/implementation_plan dir-file.md`), VidGenius quản lý tệp tin theo mô hình **CapCut/Premiere** (Project-based Directory).

Dưới đây là bản đồ tương thích lưu trữ khi chúng ta chuyển đổi hệ thống:

```
[MinIO / S3 Storage Root]
  │
  ├── jobs/                                ◄── Thư mục chuyên dùng cho Video Jobs
  │    └── {job_id}_{video_name}/          
  │         ├── script.json
  │         ├── voice_timeline_tmp.mp3     ◄── Các file TTS trung gian của Video giữ nguyên tại đây
  │         └── output/
  │              └── final_video.mp4       ◄── Thành phẩm video xuất ra
  │
  └── projects/                            ◄── Thư mục chuyên dùng cho Standalone Assets
       └── {project_id}/
            ├── audio/
            │    └── tts_{uuid}.mp3        ◄── Standalone TTS từ Speech Studio lưu tại đây
            └── images/
                 └── flux_{uuid}.png       ◄── Standalone Image từ Image Studio lưu tại đây
```

### Đánh giá sự tương thích:
1. **TTS phục vụ dựng hình (Intermediate TTS):** Khi chạy các pipeline video (`worker_unbox`, `worker_translify`), các file giọng đọc (.mp3/.wav) sinh ra cho từng phân cảnh vẫn sẽ được lưu trữ trực tiếp tại thư mục dự án `jobs/{job_id}_{video_name}/` như cũ. Điều này **hoàn toàn tương thích** với cấu trúc lưu trữ hiện tại.
2. **TTS độc lập (Speech Studio - Standalone TTS):** Người dùng nhập text để tải âm thanh về hoặc nghe thử. Thay vì tạo một Job ảo trong `video_jobs`, tệp tin sẽ được lưu trữ trực tiếp vào thư mục tài nguyên dự án: `projects/{project_id}/audio/` và được đăng ký làm một bản ghi thực thể **`Asset`** trong DB (với `source="tts"`).
3. **Ảnh nghệ thuật độc lập (Image Studio - Standalone Image):** Tương tự như TTS độc lập, ảnh sinh ra bởi FLUX sẽ được lưu trữ tại `projects/{project_id}/images/` và được đăng ký làm thực thể **`Asset`** trong DB (với `source="text2img"`).

---

## 2. Giải Pháp Thiết Kế Tối Ưu: Tái Sử Dụng Thực Thể `Asset`

Một phát kiến quan trọng khi phân tích sâu cấu trúc thư mục của VidGenius: **Chúng ta không cần tạo thêm các bảng như `audio_generations` hay `image_generations` nếu chúng ta tận dụng triệt để thực thể `Asset` sẵn có.**

Bảng `assets` hiện tại trong tệp `shared_core/models.py` đã sở hữu đầy đủ các thuộc tính cần thiết:
* `id`, `user_id`, `created_at`
* `asset_type` (chỉ định `"audio"` cho TTS, `"image"` cho FLUX)
* `file_name`, `file_size_bytes`, `mime_type`
* `s3_url` (đường dẫn trực tiếp trên MinIO)
* `folder_id` (liên kết thư mục cha `MediaFolder` trên giao diện)
* `source` (chỉ định nguồn tạo ra: `"tts"` hoặc `"text2img"`)

### Ưu điểm vượt trội của giải pháp này:
1. **Kế thừa 100% Cơ chế Hard Delete (Xóa vật lý triệt để):** 
   Khi người dùng click xóa tệp âm thanh hoặc ảnh tĩnh trên giao diện, API xóa của hệ thống sẵn có sẽ tự động gọi lệnh `delete_object` giải phóng dung lượng trên MinIO, sau đó cascade xóa bản ghi DB trong bảng `assets`. Chúng ta không cần viết thêm bất kỳ logic dọn dẹp ổ cứng tùy biến nào khác.
2. **Hiển thị trực tiếp trên Thư viện tài nguyên (Asset Library UI):**
   Vì các tệp sinh ra được đăng ký trực tiếp là một `Asset`, chúng sẽ lập tức xuất hiện trong thư mục được chọn của Asset Library. Người dùng có thể kéo thả tệp giọng đọc TTS hoặc ảnh tĩnh FLUX vừa tạo vào bất kỳ kịch bản video nào khác một cách dễ dàng.
3. **Không làm loãng cơ sở dữ liệu:** Không phát sinh bảng thừa, bảo trì chỉ mục (Index) hiệu quả hơn.

---

## 3. Phân Tích Đánh Giá Ảnh Hưởng Tới Hệ Thống (System Impact Analysis)

Việc chuyển dịch từ cơ chế chạy hàng đợi Celery chậm (qua `video_jobs`) sang API nhanh hoặc tác vụ riêng biệt cho Chat, TTS, và Sinh ảnh sẽ tạo ra các tác động sau:

### Tác động 1: Cơ chế Polling Job trên Frontend
* **Hiện trạng:** Frontend đang sử dụng cơ chế poll định kỳ API `/api/jobs/{job_id}` để theo dõi tiến trình của mọi tác vụ.
* **Ảnh hưởng:** Khi loại bỏ Chat, TTS độc lập khỏi `video_jobs`, API `/api/jobs` sẽ không còn nhận các yêu cầu này nữa.
* **Giải pháp khắc phục:**
  * **Đối với Chat:** Chuyển sang kết nối trực tiếp gọi API `/api/chat/sessions/...` thời gian thực (được tối ưu hóa bằng SSE/streaming). Giao diện chat mượt mà, phản hồi ngay lập tức và không còn độ trễ do hàng đợi Celery.
  * **Đối với TTS:** Vì Edge-TTS xử lý cực kỳ nhanh (~1.5 giây), chúng ta chuyển sang gọi API **Synchronous REST**. API sẽ xử lý xong, upload lên MinIO, lưu DB vào bảng `assets` và trả về đối tượng `Asset` ngay lập tức cho client. Frontend nhận kết quả trực tiếp từ HTTP Response mà không cần qua cơ chế Polling phức tạp!
  * **Đối với Image Studio (Text2Img):** Do sinh ảnh mất khoảng 5-10 giây trên GPU, chúng ta có thể sử dụng một API hàng đợi siêu nhẹ chuyên biệt `/api/assets/generate-image` và poll trực tiếp trạng thái tệp tin thông qua `/api/assets/{asset_id}`.

### Tác động 2: Tính năng Nhân bản Job (Copy/Clone Job)
* **Hiện trạng:** Khi nhân bản một Video Job, hệ thống sẽ ánh xạ và tham chiếu các Assets đầu vào.
* **Ảnh hưởng:** Nếu các âm thanh TTS độc lập và ảnh sinh ra trước đó được lưu trữ dưới dạng `Asset` chuẩn trong thư mục Asset Library, chúng sẽ được đối xử như các tài nguyên thô tải lên (raw uploads) bình thường.
* **Giải pháp khắc phục:** **Không cần chỉnh sửa.** Cơ chế Clone Job hiện có sẽ tự động hoạt động hoàn hảo và độc lập mà không gặp bất kỳ xung đột nào, vì các tệp sinh ra đã là các `Asset` chuẩn mực có ID riêng biệt.

---

## 4. Bảng Đánh Giá Rủi Ro & Biện Pháp Đảm Bảo An Toàn

| Vùng ảnh hưởng | Mức độ rủi ro | Chi tiết ảnh hưởng | Biện pháp đảm bảo an toàn (Mitigation) |
| :--- | :--- | :--- | :--- |
| **Backward Compatibility (Tương thích ngược API)** | **Trung bình** | Các client cũ hoặc code Frontend chưa cập nhật vẫn cố gắng gửi job chat/tts lên endpoint `/api/jobs`. | Giữ lại các router cũ trong `/api/jobs` làm cổng chuyển tiếp tạm thời (Deprecated). Nếu nhận `job_type="chat"` hoặc `"tts"`, API sẽ tự động định tuyến lại và gọi ngầm đến kiến trúc mới, trả về cấu trúc tương thích ngược trước khi xóa bỏ hoàn toàn ở phiên bản sau. |
| **MinIO Storage Orphan Files (Tệp rác vật lý)** | **Thấp** | Quá trình sinh ảnh/âm thanh thất bại giữa chừng có thể để lại tệp nháp trên MinIO mà không có bản ghi `Asset` trong DB. | Triển khai cơ chế Transaction an toàn: Tải tệp lên MinIO thành công trước, sau đó lưu DB. Nếu lưu DB lỗi, chạy lệnh `delete_object` thu hồi ngay lập tức trong khối `except` của Backend API. |
| **Database Migrations (Alembic)** | **Thấp** | Việc tạo mới các bảng chat (`chat_sessions`, `chat_messages`) có khóa ngoại liên kết với bảng `users` và `projects`. | Viết kịch bản migration chi tiết với đầy đủ các điều kiện ràng buộc khóa ngoại có thuộc tính `ondelete="CASCADE"`. Tránh xung đột khóa ngoại bằng cách chạy kiểm thử migration trên SQLite/PostgreSQL development trước khi đưa lên production. |

---

## 5. Kết Luận Chung

* **Tính tương thích với Thư mục & MinIO:** Đạt mức **Tương thích Tuyệt đối (100% Compatible)**. Việc tận dụng thực thể `Asset` giúp các tệp sinh ra từ TTS độc lập và ảnh tĩnh FLUX hòa nhập hoàn hảo vào mô hình cây thư mục dự án và cơ chế xóa triệt để vật lý (Hard Delete) trên MinIO.
* **Ảnh hưởng hệ thống:** Hoàn toàn trong tầm kiểm soát. Giải pháp khắc phục thông qua việc chuyển đổi luồng Polling sang gọi API trực tiếp và duy trì tương thích ngược tạm thời sẽ giúp VidGenius lột xác thành một hệ thống mượt mà, chuyên nghiệp và có kiến trúc lưu trữ dữ liệu chuẩn mực nhất.
