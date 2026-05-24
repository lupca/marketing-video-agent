# Tài Liệu Kỹ Thuật: Tái Cấu Trúc Sidebar & Hệ Thống AI Addon Toàn Cầu

Tài liệu này cung cấp cái nhìn chi tiết về kiến trúc phần mềm, mô hình dữ liệu, thiết kế UI/UX và hướng dẫn bảo trì/mở rộng cho hai nâng cấp giao diện cốt lõi của **VidGenius**:
1. **Tái cấu trúc Sidebar**: Phân nhóm khoa học, hỗ trợ đóng/mở danh mục và chế độ thu nhỏ tối giản (Slim Mode).
2. **Hệ thống AI Addon Toàn cầu**: Thanh Dock nổi trợ lý, ngăn kéo slide-over đa nhiệm, bảo toàn trạng thái (State Preservation) và truyền nhanh dữ liệu (Data Deep-linking).

---

## 📂 Sơ Đồ Cấu Trúc Thư Mục Triển Khai

Mã nguồn của hệ thống nâng cấp được tổ chức mô-đun hóa cao độ và cô đọng hoàn toàn trong các tệp tin sau:

```text
frontend-admin/
├── src/
│   ├── context/
│   │   └── AIStudioAddonContext.tsx       # Quản lý State toàn cục của hệ thống Addon
│   │
│   ├── components/
│   │   └── layout/
│   │       ├── Sidebar.tsx                # Giao diện Sidebar phân nhóm & Slim Mode
│   │       └── addons/
│   │           ├── addonConfig.ts         # Addon Registry - Đăng ký Addon trung tâm
│   │           ├── AIAddonDock.tsx        # Thanh Dock nổi kính mờ mép phải màn hình
│   │           ├── AIAddonDrawer.tsx      # Ngăn kéo trượt đa nhiệm chứa các Widgets
│   │           └── widgets/
│   │               ├── AgentChatWidget.tsx    # Widget Chat AI tư vấn, sao chép nhanh kịch bản
│   │               ├── ImageStudioWidget.tsx  # Widget Gen ảnh FLUX nhanh, lưu vào Assets
│   │               ├── SpeechStudioWidget.tsx # Widget TTS MeloTTS lồng tiếng, nhận kịch bản
│   │               └── VideoDownloadWidget.tsx # Widget Tải video nguyên liệu thô từ link
│   │
│   └── App.tsx                            # Tích hợp Provider toàn cục & Mount Layout
```

---

## 1. Tái Cấu Trúc Sidebar (Sidebar Redesign)

### 💎 Điểm Nhấn Trải Nghiệm (UX Upgrades)
- **Phân nhóm khoa học**: Giảm tải thị giác bằng cách nhóm 16 mục điều hướng rối rắm thành 4 nhóm danh mục logic: *Tổng quan & Dự án, Xưởng Video AI, AI Studio Hỗ trợ* và *Hệ thống & Tài liệu*.
- **Ghi nhớ Accordion**: Người dùng có thể thu gọn/mở rộng từng danh mục. Trạng thái đóng/mở được đồng bộ tự động vào `localStorage` giúp giữ nguyên thiết lập khi F5 tải lại trang.
- **Slim Mode (w-20)**: Chỉ hiển thị Icon giúp mở rộng tối đa không gian làm việc của các màn hình biểu mẫu dài hoặc chỉnh sửa video nặng (ví dụ: Translify Editor).
- **Active Glow Neon**: Icon của liên kết đang truy cập sẽ có hiệu ứng đổ bóng phát sáng neon tím mờ, viền nổi nhẹ và một dải phát sáng nhỏ ở lề trái.

### ⚙️ Logic Kỹ Thuật (Sidebar.tsx)
- Cấu trúc dữ liệu liên kết:
  ```typescript
  interface SidebarLink {
    name: string;
    path: string;
    icon: React.ComponentType<any>;
    description: string; // Sử dụng để hiển thị tooltip khi Sidebar thu nhỏ
  }
  ```
- **Slim Mode** được quản lý bằng state `isSlim` lưu trong `localStorage`. Khi `isSlim === true`, Sidebar chuyển chiều rộng từ `w-64` thành `w-20`, ẩn các tiêu đề nhóm, ẩn text liên kết và chuyển đổi User Profile chân trang thành tooltip popup chứa nút Đăng xuất.
- Kèm theo **Premium Tooltips** thiết kế theo chuẩn glassmorphism trượt mượt mà sang bên phải khi rê chuột vào các biểu tượng ở chế độ Slim Mode.

---

## 2. Hệ Thống AI Addon Toàn Cầu (Global AI Addon System)

Hệ thống Addon được xây dựng để hỗ trợ đắc lực cho quy trình sáng tạo nội dung của Creator. Nó giải quyết bài toán: *"Đang soạn kịch bản video/unbox dở tay mà cần gen ảnh hoặc thuyết minh gấp thì làm thế nào?"*

### 💡 Triết Lý Thiết Kế UX
1. **State Preservation (Bảo toàn trạng thái)**:
   - Các Addon không chạy dưới dạng các trang route riêng biệt, mà chạy như các **Overlay Drawer (Bảng trượt cạnh phải)**.
   - Nhờ mount ở cấp Layout cốt lõi (`MainLayout` trong `App.tsx`), việc mở/đóng các Addon đè lên trang chính hoàn toàn không làm đổi route, không tải lại trang và **giữ nguyên 100% dữ liệu form mà người dùng đang nhập dở** ở phía dưới.
2. **Data Deep-linking (Liên kết sâu dữ liệu)**:
   - Cung cấp khả năng nạp dữ liệu nhanh từ trang chính vào Widget Addon thông qua biến toàn cục `initialData`.
   - Trang chính có thể kích hoạt nhanh Addon bằng cách gọi hàm `openAddon("speech_studio", { text: "đoạn văn bản cần đọc" })`. Trợ lý thuyết minh sẽ tự động trượt ra và điền sẵn văn bản đó cho người dùng.

### 🏗️ Kiến Trúc Hệ Thống (Addon Registry)
Kiến trúc này cho phép **mở rộng vô hạn các addon hỗ trợ mới** trong tương lai mà không làm ảnh hưởng đến mã nguồn cốt lõi của ứng dụng.

Mọi Addon được đăng ký tập trung trong tệp tin **[addonConfig.ts](file:///wsl.localhost/server/root/marketing-video-agent/frontend-admin/src/components/layout/addons/addonConfig.ts)**:
```typescript
export interface AIAddon {
  id: string;
  name: string;
  icon: React.ComponentType<any>;
  description: string;
  component: React.ComponentType<any>; // React Component giao diện Widget rút gọn
}

export const AI_ADDONS: AIAddon[] = [
  // Danh sách các Addon hỗ trợ đăng ký
];
```

#### 🚀 Cách Thêm Một Addon Mới (Dành Cho Lập Trình Viên):
Khi bạn muốn tạo một công cụ hỗ trợ mới (ví dụ: **AI Music Studio Widget**):
1. **Bước 1**: Tạo file widget giao diện rút gọn mới tại:
   `src/components/layout/addons/widgets/MusicStudioWidget.tsx`
2. **Bước 2**: Mở file `src/components/layout/addons/addonConfig.ts`, import widget mới và thêm khai báo đối tượng vào mảng `AI_ADDONS`:
   ```typescript
   import MusicStudioWidget from "./widgets/MusicStudioWidget";
   import { Music } from "lucide-react";

   export const AI_ADDONS: AIAddon[] = [
     // ... các addon hiện tại
     {
       id: "music_studio",
       name: "Music Studio",
       icon: Music,
       description: "Tạo nhạc nền AI khớp beat video nhanh chóng",
       component: MusicStudioWidget
     }
   ];
   ```
3. **Kết quả**: **Xong!** Thanh Dock nổi bên phải sẽ tự động vẽ thêm nút Icon nốt nhạc, rê chuột có tooltip hướng dẫn và click sẽ tự động trượt Drawer hiển thị đúng giao diện `MusicStudioWidget` trên toàn bộ tất cả mọi trang của hệ thống!

---

## 3. Chi Tiết Hoạt Động Của Các Widgets

1. **Trợ Lý AI (AgentChatWidget)**:
   - Giao diện chat thời gian thực. Đề xuất nhanh các nút tạo kịch bản, prompt ảnh FLUX, dịch thuật Việt-Anh.
   - Đặc biệt tích hợp nút **Copy** ở góc dưới mỗi câu trả lời của AI, hỗ trợ sao chép nhanh văn bản vào khay nhớ tạm để dán thẳng vào các biểu mẫu làm việc ở màn hình chính.
2. **Image Studio Widget (ImageStudioWidget)**:
   - Bản rút gọn hiệu năng cao tích hợp API gen ảnh FLUX.1.
   - Hỗ trợ chọn Dự án, gõ mô tả prompt, chọn tỉ lệ khung hình (1:1, 16:9, 9:16), bấm Gen trực tiếp, xem ảnh preview và nhấn **Lưu vào Assets** dự án tức thì.
3. **Speech Studio Widget (SpeechStudioWidget)**:
   - Bản rút gọn thuyết minh lồng tiếng qua Edge-TTS / MeloTTS.
   - Nhận diện liên kết sâu dữ liệu kịch bản, hỗ trợ nghe thử trực tiếp tại chỗ trước khi nhấn **Lưu vào Assets** dự án.
4. **Sưu tầm Video (VideoDownloadWidget)**:
   - Dán nhanh đường link tải video/audio thô từ các mạng xã hội (YouTube, TikTok, v.v.), Render Farm sẽ tải ngầm và tự động đẩy vào kho tài nguyên.

---

## 🧪 Xác Minh Hoạt Động

Dự án đã được biên dịch toàn diện để xác minh tính ổn định của mã nguồn mới:
```bash
wsl sh -c "cd /root/marketing-video-agent/frontend-admin && npm run build"
```
**Kết quả**: Quá trình kiểm tra kiểu dữ liệu (Type-Checking) TypeScript hoàn toàn sạch sẽ, **không phát sinh bất kỳ lỗi hay cảnh báo cảnh báo nào** liên quan đến Sidebar và hệ thống Addon.
