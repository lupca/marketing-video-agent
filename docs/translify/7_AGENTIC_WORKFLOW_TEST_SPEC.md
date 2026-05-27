# Test Specification: Agentic LangGraph Translify Workflow

Bản tài liệu đặc tả kỹ thuật kiểm thử (Test Specification) này hướng dẫn chi tiết phương pháp kiểm thử đơn vị (Unit Test - UT) và kiểm thử thực tế (Integration Test - IT) cho hệ thống **Agentic LangGraph Translify Workflow** nâng cấp.

---

## 1. Đặc Tả Kiểm Thử Đơn Vị (Unit Test Spec)

Mã nguồn kiểm thử đơn vị được cài đặt tại file [test_translify_graph.py](file:///wsl.localhost/server/root/marketing-video-agent/tests/test_translify_graph.py). Bộ test sử dụng kỹ thuật Mocking chuyên sâu (`unittest.mock`) để cách ly luồng xử lý đồ thị khỏi môi trường thực tế, loại bỏ phụ thuộc vào API Key bên ngoài và kết nối DB trực tiếp nhằm tối ưu hóa tốc độ và độ ổn định khi chạy CI/CD.

### UT Case 1: Trích Xuất JSON Phòng Thủ (`extract_json_from_text`)
- **Mục tiêu:** Đảm bảo hàm bóc tách dữ liệu JSON hoạt động trơn tru trước bất kỳ định dạng văn bản thô nào trả về từ LLM (bao gồm cả khối suy nghĩ `<think>...</think>` của DeepSeek/Qwen và khối markdown ` ```json ... ``` `).
- **Kịch bản kiểm thử:**
  1. *Đầu vào đơn giản:* `{"key": "value"}` $\rightarrow$ Kết quả: Parse thành công.
  2. *Đầu vào Markdown bọc suy nghĩ:* `<think>reasoning</think>\n```json\n{"key": "value"}\n``` $\rightarrow$ Kết quả: Tự động loại bỏ suy nghĩ và codeblock, parse thành công.
  3. *Đầu vào văn bản thô bao quanh:* `Here is results: {"key": "value"} hope it helps` $\rightarrow$ Kết quả: Bóc tách lớp ngoặc nhọn ngoài cùng, parse thành công.

### UT Case 2: Node 1 — Glossary Extractor
- **Mục tiêu:** Kiểm tra khả năng thu thập transcript tiếng Trung của tất cả phân cảnh, gọi LLM phân tích, và ghi nhận lại `theme_summary` cùng bảng thuật ngữ `glossary` vào State.
- **Dữ liệu giả lập (Mock assertions):**
  - Xác nhận LLM nhận vào đúng tham số nhiệt độ thấp `temperature=0.1` để tăng tính chính xác.
  - Xác nhận đầu ra ghi nhận chính xác 2 cấu trúc thông tin vào State.

### UT Case 3: Node 2 — Sliding Translation (Dịch trượt)
- **Mục tiêu:** Xác minh luồng duyệt trực tiếp mảng `scenes` (không dùng SpaCy), lấy biên lề ngữ cảnh của phân cảnh liền kề trước ($i-1$) và sau ($i+1$) nạp vào prompt để LLM dịch sát nghĩa.
- **Kịch bản kiểm thử:**
  - Đối với phân cảnh 1 ($i=0$): Phân cảnh trước ($i-1$) phải là "Không có (Bắt đầu video)".
  - Đối với phân cảnh cuối ($i=N-1$): Phân cảnh sau ($i+1$) phải là "Không có (Kết thúc video)".
  - Đồng thời kiểm tra tích hợp tự động dịch danh sách chữ cứng (OCR Items) theo phân cảnh bằng LLM và điền vào trường `text_vi` của mỗi OCR Item.

### UT Case 4: Node 3 — Reflective Adaptation (Hiệu chỉnh Việt hóa)
- **Mục tiêu:** Kiểm duyệt khả năng gọi LLM đóng vai trò Biên tập viên bản địa hóa, đánh giá câu thoại sát nghĩa, và điều chỉnh văn phong tự nhiên khớp với `campaign_tone` truyền vào (ví dụ: casual, tutorial, TikTok).

### UT Case 5: Node 4 — Pacing Validator (Python-only)
- **Mục tiêu:** Đo đạc nhịp độ chữ tiếng Việt của từng cảnh. Đảm bảo cảnh nào có tốc độ nói vượt quá giới hạn **4.0 từ/giây** (`word_count > max(1, int(duration * 4.0))`) sẽ lập tức bị gán ID vào danh sách `pacing_violations` để chuyển rẽ nhánh.

### UT Case 6: Node 5 — Trimming Agent (LLM Loop)
- **Mục tiêu:** Đảm bảo đồ thị LangGraph rẽ nhánh sang Trimming Node khi phát hiện vi phạm nhịp độ chữ, kích hoạt LLM viết gọn lại câu thoại (bỏ từ đệm *nha, nhé*, rút từ bổ nghĩa) và tăng số lần thử `trimming_attempts` lên 1 đơn vị.

### UT Case 7: Node 6 — Fallback Healing (Lưới an toàn)
- **Mục tiêu:** Kiểm tra trường hợp đặc biệt khi câu thoại vẫn quá dài sau 3 lần thử thích ứng. Python Healer phải can thiệp cắt tỉa vật lý lấy đúng số lượng từ tối đa an toàn bên trái (`" ".join(words[:max_words])`) để bảo toàn thời lượng.

### UT Case 8: Node 7 — Persistence (Đồng bộ & Lưu trữ)
- **Mục tiêu:** Xác nhận logic đồng bộ cuối cùng của Stage 1:
  1. Tải file vocal/bgm trung gian lên kho lưu trữ MinIO S3.
  2. Đăng ký tài nguyên vào bảng `Asset` trong CSDL.
  3. Ghi đè kịch bản `VideoProject` sạch vào trường `config_data` của bảng `VideoJob`.
  4. Chuyển trạng thái Job sang **`WAITING_FOR_REVIEW`** và kết xuất Graph.

---

## 2. Kiểm Thử Đồ Thị Thực Tế Với Live LLM (Integration Test)

Để thực thi kiểm thử đồ thị thực tế trên các file media và gọi Live LLM (Ollama hoặc OpenAI) mà không cần qua giao diện Frontend, nhà phát triển sử dụng công cụ dry-runner chạy trực tiếp bằng lệnh Python.

Chúng tôi cung cấp sẵn kịch bản chạy dry-run tại đường dẫn [run_real_translify_dryrun.py](file:///wsl.localhost/server/root/marketing-video-agent/scratch/run_real_translify_dryrun.py).

### Bước 1: Chuẩn bị môi trường Live LLM
Đảm bảo Ollama cục bộ đang chạy hoặc cấu hình API Key trong cơ sở dữ liệu đã được nạp:
```bash
# Kiểm tra dịch vụ Ollama cục bộ có hoạt động (mặc định model qwen2.5:14b)
curl http://localhost:11434/api/tags
```

### Bước 2: Kích hoạt môi trường và thực thi Dry-Run
Chạy tập lệnh dry-run bằng trình thông dịch của virtual environment `.venv-light` chứa đầy đủ thư viện LangGraph:

```bash
# Di chuyển vào thư mục dự án
cd /root/marketing-video-agent

# Chạy dry-run với video mặc định của hệ thống
.venv-light/bin/python3 scratch/run_real_translify_dryrun.py --video tests/test_rc.mp4 --tone "trực quan, trẻ trung, TikTok"
```

### Bước 3: Xem kết quả và vết log Agent
Tập lệnh dry-run sẽ chạy toàn bộ 7 nodes một cách đồng bộ và kết xuất:
1. **Live Job Logs:** Tiến trình thực thi đồ thị in thời gian thực.
2. **Database Trace:** Toàn bộ thông tin đầu vào, đầu ra, và suy nghĩ reasoning của LLM được lưu giữ trực tiếp tại bảng `agent_logs` (xem qua API `/api/jobs/{job_id}/trace` hoặc dùng SQL client).
3. **Database Status:** Bản ghi `VideoJob` chuyển trạng thái về `WAITING_FOR_REVIEW` và sẵn sàng hiển thị trên giao diện duyệt phụ đề của người dùng.
