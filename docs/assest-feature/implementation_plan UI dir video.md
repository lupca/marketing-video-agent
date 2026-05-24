# Kế hoạch Nâng Cấp Giao Diện Giao Diện Người Dùng (Frontend-admin Asset Library)

**Mục tiêu:** Xây dựng một giao diện Asset Library (Trình quản lý tệp) hiện đại, cao cấp với phong cách Glassmorphism và tối ưu UX vượt trội. Người dùng có thể dễ dàng quản lý tệp tin, tạo thư mục con đa cấp, kéo thả, di chuyển, đổi tên trực quan giống như **Canva** và **Google Drive**.

---

## Thiết Kế Trải Nghiệm Giao Diện (UI/UX Design)

### 1.1. Cấu Trúc Bố Cục 2 Cột Cao Cấp
* **Left Sidebar (Thanh Điều Hướng Phụ):**
  - 📂 **My Files:** Thư mục gốc chứa toàn bộ dữ liệu tải lên (`folder_id = root`).
  - ✨ **AI Generations:** Lọc trực tiếp các thư mục và file do AI Workers sinh ra (`is_job_folder = true` hoặc `source = "generated"`). Gom toàn bộ kết quả Gen Video/Ảnh của từng dự án thành các folder riêng biệt mang tên Video/Job đó.
* **Main Area (Vùng làm việc chính):**
  - **Breadcrumbs (Đường dẫn):** Điều hướng linh hoạt, ví dụ: `My Files > Dự án A > Kịch bản Tết 2026`. Click vào từng thành phần để quay lại thư mục cha tương ứng.
  - **Grid & List Toggle:** Hỗ trợ xem dạng lưới (Grid View) với thumbnail xem trước cỡ lớn (video player mini, audio waveform, image preview) hoặc dạng danh sách (List View) chi tiết thông tin.
  - **Action Header:** Nút "New Folder" (Tạo thư mục) và "Upload File" (Tải tệp lên thư mục hiện tại).

### 1.2. Micro-Interactions (Hiệu Ứng Trải Nghiệm Đỉnh Cao)
* **Đúp click để vào thư mục (Double Click):** Giống như máy tính cá nhân hoặc Google Drive.
* **Inline Rename (Đổi tên nhanh):** Bấm đúp chậm vào tên file/folder hoặc chọn "Rename" để biến văn bản thành ô Input nhập liệu trực tiếp tại chỗ, bấm Enter để gửi API lưu tên mới.
* **Badges AI Generations:** Các file do AI tự động sinh ra có một Icon lấp lánh ✨ kèm Badge nhỏ `AI Generated` để tạo điểm nhấn premium.

---

## 2. Kế Hoạch Thay Đổi Cấu Trúc Code Frontend

### 2.1. Cập nhật `src/hooks/useAssets.ts`
Bổ sung các hàm tương tác với API mới đã hoàn thiện ở backend:
- `folders`: Lưu danh sách các thư mục.
- `currentFolderId`: State quản lý thư mục hiện tại (mặc định: `'root'`).
- `fetchFolders()`: Gọi `GET /api/folders` để lấy cấu trúc thư mục của user.
- `createFolder(name, parentId)`: Gọi `POST /api/folders` để tạo thư mục ảo mới.
- `updateFolder(id, name, parentId)`: Gọi `PUT /api/folders/{id}` để đổi tên hoặc di chuyển thư mục.
- `deleteFolder(id)`: Gọi `DELETE /api/folders/{id}` để xóa thư mục đệ quy (Hard Delete).
- `updateAsset(id, displayName, folderId)`: Gọi `PUT /api/assets/{id}` để đổi tên hiển thị hoặc di chuyển tệp.

### 2.2. Nâng cấp Component `src/components/features/assets/AssetTable.tsx`
- Thay thế hoàn toàn logic tự tách chuỗi `/` cũ thành việc hiển thị danh sách `folders` và `files` chính thức từ cơ sở dữ liệu dựa trên `folder_id` hiện tại.
- Thêm **Context Menu** (hoặc Nút 3 chấm `...`) ở từng Folder và File để cung cấp các lựa chọn:
  - **Rename:** Đổi tên nhanh trực quan.
  - **Move to...:** Hiện Modal hiển thị cây thư mục để người dùng chọn di chuyển File/Folder.
  - **Delete:** Gọi API Hard Delete.
  - **Download:** Tải tệp tin.

### 2.3. Cập nhật Trang `src/pages/Assets.tsx`
- Tích hợp Modal "Move To Folder" hiển thị cây thư mục ảo dạng sơ đồ cây để người dùng chọn thư mục đích.
- Tích hợp tính năng tạo thư mục mới thông qua popup/modal.
- Khi Upload file, tự động đính kèm `folder_id` hiện tại vào Payload `FormData` gửi lên Backend.

---


  - Viết các hàm fetch folders, CRUD folder, và cập nhật asset.
  - Xây dựng modal hiển thị sơ đồ cây thư mục của người dùng giúp di chuyển tệp dễ dàng.
  - Hiển thị danh sách Folders và Files chuẩn từ database.
  - Tích hợp Inline Rename (đổi tên trực quan).
  - Tích hợp Context Menu 3 chấm hành động.
  - Tích hợp Left Sidebar phân loại My Files & AI Generations.
  - Tích hợp Breadcrumbs mượt mà.
  - Tích hợp hiệu ứng Double Click mở thư mục.
