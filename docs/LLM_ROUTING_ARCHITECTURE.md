# Kiến Trúc Chọn Lọc & Điều Phối LLM (User-Centric LLM Routing Architecture)

Tài liệu này mô tả thiết kế kiến trúc dài hạn cho việc quản lý, cấu hình và phân luồng (routing) các mô hình AI/LLM trong Video Creator Platform.

## 1. Triết Lý Thiết Kế (Design Philosophy)

*   **User-Centric (Lấy User làm trung tâm):** Cấu hình AI phải đi theo tài khoản User. Hỗ trợ cơ chế BYOK (Bring Your Own Key), cho phép user sử dụng API Key cá nhân để không phụ thuộc hoặc tiêu tốn tài nguyên chung.
*   **Future-Proof (Chống lỗi thời):** Sử dụng `feature_key` linh hoạt dạng chuỗi thay vì hardcode biến trong DB/Code. Khi có tính năng AI mới (VD: tạo tiêu đề SEO, phân tích ảnh), chỉ cần gọi đúng tên tính năng, hệ thống tự động fallback mà không cần chạy DB Migration.
*   **DRY (Don't Repeat Yourself):** Mọi logic "Tìm xem dùng model nào, API key là gì, Base URL là gì" được gom về **MỘT** nơi duy nhất (The Resolver). Các worker/agent không tự đọc `.env` hay tự query bảng setting nữa.
*   **Hierarchical Fallback (Cơ chế phân cấp ưu tiên):** Đảm bảo không bao giờ bị crash vì thiếu model. `User Override -> Global Feature Routing -> Global Default -> Hardcoded Environment Default`.

---

## 2. Kiến Trúc Dữ Liệu (Data Architecture)

Không tạo thêm bảng mới, tận dụng sức mạnh của cột JSONB trong PostgreSQL để cấu trúc linh hoạt.

### 2.1. Cấu hình cấp Hệ Thống (Global - Admin)
Nằm trong bảng `SystemSetting` (key-value store).
*   **Key `llm_models`**: Chứa danh sách TẤT CẢ các model công ty cung cấp (Ollama, OpenAI chung,...).
    ```json
    [
      {"id": "sys-gpt4o", "provider": "openai", "name": "System GPT-4o", "base_url": "...", "model_name": "gpt-4o", "api_key": "sk-xxx"},
      {"id": "sys-qwen25", "provider": "ollama", "name": "Local Qwen 2.5", "base_url": "...", "model_name": "qwen2.5", "api_key": ""}
    ]
    ```
*   **Key `llm_routing`**: Ánh xạ tính năng nào xài model hệ thống nào.
    ```json
    {
      "default": "sys-qwen25", 
      "leader_script_analysis": "sys-gpt4o",
      "chat_assistant": "sys-qwen25",
      "video_orchestrator": "sys-qwen25"
    }
    ```

### 2.2. Cấu hình cấp Người Dùng (User-Level - Personal)
Nằm trong bảng `User` (bổ sung cột `llm_preferences` dạng JSONB).
```json
{
  "custom_models": [
    {"id": "user-claude", "provider": "anthropic", "name": "My Claude", "base_url": "...", "model_name": "claude-3-5-sonnet", "api_key": "sk-ant-..."}
  ],
  "routing": {
    "chat_assistant": "user-claude"
  }
}
```

---

## 3. Kiến Trúc Backend (Code Architecture)

### 3.1. Thư mục `shared_core/llm_resolver.py` (MỚI)
Đây là trái tim của kiến trúc. Cung cấp hàm duy nhất cho toàn hệ thống:

```python
def resolve_llm_config(user_id: str, feature_key: str) -> dict:
    """
    Trả về Dict chứa {base_url, api_key, model_name} dựa trên mức ưu tiên.
    1. Check user routing -> user custom models
    2. Check user routing -> global models
    3. Check global routing -> global models
    4. Check global default -> global models
    5. Fallback config.py (Environment)
    """
```

### 3.2. Cập nhật các AI Workers
Xóa bỏ code tự đọc setting. Thay thế bằng Resolver.
*   `worker_chat/engine.py`: Gọi `resolve_llm_config(job.user_id, "chat_assistant")`.
*   `worker_leader/leader_runner.py`: Gọi `resolve_llm_config(job.user_id, "leader_script_analysis")`.
*   `worker_agent/agent_runner.py`: Gọi `resolve_llm_config(job.user_id, "video_orchestrator")`.

### 3.3. Cập nhật Model Schema (`shared_core/schemas.py`)
*   Định nghĩa Pydantic models cực kỳ chặt chẽ cho `LLMConfig` và `LLMPreferences` để tái sử dụng ở mọi endpoint.

---

## 4. Kiến Trúc Frontend UI (React)

### 4.1. Màn hình Cài đặt Hệ thống (Admin Settings > LLM Models)
*   Quản lý danh sách các Global Models (Thêm OpenAI, Thêm Ollama).
*   Giao diện Routing cho các Feature Key cốt lõi (Leader, Agent, Chat). 
*   *Lưu ý:* Admin chỉ route được các Global Models.

### 4.2. Màn hình Hồ sơ cá nhân (User Profile > AI Preferences)
*   Nơi user tự nhập "Custom API Keys" (chỉ lưu phía server, không log ra UI để bảo mật).
*   Giao diện Personal Routing: User có thể đè (override) model cho từng tính năng. Nếu để trống -> Dùng mặc định của hệ thống.

## 5. Kế hoạch Triển khai (Implementation Plan)

1.  **Bước 1 - Database & Core:** 
    *   Sửa file `models.py` (Thêm cột `llm_preferences` cho User).
    *   Tạo file `shared_core/llm_resolver.py` và viết Unit Test kỹ càng đảm bảo thuật toán Fallback hoạt động hoàn hảo 5 tầng.
2.  **Bước 2 - API Layer:** 
    *   Cập nhật `admin-api/routers/system_models.py` cho logic Global.
    *   Tạo mới `admin-api/routers/user_preferences.py` để xử lý lưu/đọc BYOK của user.
3.  **Bước 3 - Worker Refactoring:** 
    *   Vào `worker_chat`, `worker_leader`, `worker_agent` thay thế các đoạn code gọi Ollama tĩnh bằng hàm `resolve_llm_config`. Đảm bảo truyền đúng `user_id`.
4.  **Bước 4 - Frontend Admin & User Profile:** 
    *   Thiết kế UI trực quan, rõ ràng cho việc map tính năng với Model. (Làm sau cùng khi API đã vững).