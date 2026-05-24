# Hướng Dẫn Kỹ Thuật: Worker Vietnamese Text-to-Speech (worker_tts)

Hệ thống **Worker TTS** (`tts` job type) là một công cụ dịch vụ nền chuyên biệt chịu trách nhiệm tổng hợp, chuyển đổi văn bản kịch bản tiếng Việt thành giọng đọc thuyết minh tự động dạng tệp tin âm thanh chất lượng cao (`.mp3` / `.wav`), lưu trữ lên S3 và đăng ký trực tiếp vào thư viện tài nguyên của người dùng.

---

## 🏗️ 1. Sơ Đồ Hoạt Động Tổng Quan (Workflow Architecture)

Dưới đây là luồng xử lý khép kín của một tác vụ sinh giọng thuyết minh tiếng Việt:

```mermaid
graph TD
    A[Admin API: POST /api/jobs] -->|Submit TTS Job| B[(Database VideoJob PENDING)]
    A -->|Push Task to tts_queue| C((Redis Broker))
    C -->|Deliver Task| D[worker_tts Celery Node]
    
    subgraph Celery Task Execution
        D -->|1. Parse payload| E{Model Choice?}
        E -->|model="melotts"| F[MeloTTS API Port 8000]
        E -->|model="edge-tts"| G[Edge-TTS HoaiMy / NamMinh]
        
        F & G -->|2. Generate Local| H[Local Temp File: /tmp/uuid.mp3]
        H -->|3. S3 Upload| I[Upload File to MinIO]
    end
    
    I -->|4. Register Asset| J[(Database Asset Table)]
    I -->|5. Update Job Status SUCCESS| B
    J -->|6. Render in Asset Library| K[React Web Admin UI]
```

---

## 🎙️ 2. Các Mô Hình Thuyết Minh Tích Hợp (Voice Providers)

Để tối ưu hóa độ truyền cảm và tốc độ sinh thoại, Worker TTS tích hợp song song hai nền tảng sinh thoại:

### A. Mô Hình Cục Bộ MeloTTS (`melotts`)
- **Đặc trưng**: Mô hình học sâu chuyên biệt cho tiếng Việt chạy local trên máy chủ.
- **API Endpoint**: `http://127.0.0.1:8000/tts` (hoặc cấu hình tùy biến qua biến môi trường `TTS_API_URL`).
- **Ưu điểm**: Khởi chạy offline hoàn toàn, tốc độ render cực nhanh (~0.8s cho 1 câu), không phụ thuộc kết nối Internet và không lo bị giới hạn băng thông.

### B. Mô Hình Microsoft Edge-TTS (`edge-tts`)
- **Đặc trưng**: Dịch vụ đám mây miễn phí và không yêu cầu API Key của Microsoft.
- **Giọng đọc tích hợp**:
  - `vi-VN-HoaiMyNeural`: Giọng đọc nữ miền Nam vô cùng truyền cảm, tự nhiên, thích hợp cho kịch bản review mỹ phẩm, thời trang.
  - `vi-VN-NamMinhNeural`: Giọng đọc nam miền Bắc trầm ấm, dứt khoát, thích hợp cho kịch bản review công nghệ, thể thao, tin tức.
- **Co giãn tốc độ (Speed-Stretching)**: Tự động chuyển đổi tỷ lệ số thực `speed = 1.0 | 1.2 | 0.8` sang định dạng phần trăm của Edge-TTS (ví dụ: `+20%` hoặc `-10%`).

---

## 📝 3. Đặc Tả Dữ Liệu Đầu Vào (Input Configuration)

Khi gọi API `/api/jobs` để sinh thoại, cấu hình `config_data` cần tuân thủ cấu trúc sau:

```json
{
  "project_id": "cfa3817a-8b82-42d8-9993-9c87d8ccb909",
  "job_type": "tts",
  "config_data": {
    "title": "Voiceover Giới Thiệu Son Môi",
    "text": "Chào các bạn! Hôm nay mình sẽ đập hộp thỏi son hot trend nhất năm nay nhé.",
    "model": "edge-tts",               // Tùy chọn: "melotts" (mặc định) hoặc "edge-tts"
    "speaker": "vi-VN-HoaiMyNeural",   // Tùy chọn: tên voice Edge hoặc mã speaker MeloTTS
    "speed": 1.05                      // Tùy chọn: tốc độ nói (từ 0.5 đến 2.0)
  }
}
```

---

## 📂 4. Kiến Trúc Lưu Trữ (S3 Storage & Asset Registry)

Sau khi tệp âm thanh `.mp3` được sinh ra tạm thời tại thư mục `/tmp/` local, Worker thực hiện quy trình tự động đồng bộ hóa lên đám mây:

### A. Phân Rã Đường Dẫn Trên MinIO S3
Đường dẫn lưu trữ vật lý của file thoại tự động phân loại theo ngữ cảnh sử dụng:

1. **TTS Dựng Video (Intermediate TTS)**: Sinh thoại tự động cho từng phân cảnh của pipeline video.
   - *Đường dẫn*: `jobs/{job_id}_{video_name_cleaned}/output/tts_{job_id}_{timestamp}.mp3`
   - *Mục đích*: Cô lập hoàn toàn tài nguyên trung gian của job dựng video để dễ dàng dọn dẹp khi xóa job.
2. **TTS Độc Lập (Speech Studio - Standalone TTS)**: Người dùng nhập văn bản để tải thoại về.
   - *Đường dẫn*: `projects/{project_id}/audio/tts_{job_id}_{timestamp}.mp3`
   - *Mục đích*: Lưu trữ lâu dài làm tài nguyên thô dùng chung.

### B. Tự Động Đăng Ký Tài Nguyên (Asset Registry)
Để người dùng có thể tái sử dụng file âm thanh thuyết minh vừa sinh ra, Worker kết nối vào database PostgreSQL để thực hiện đăng ký làm một thực thể **`Asset`** chuẩn mực:

```python
asset = Asset(
    user_id=user_id,
    asset_type="audio",
    file_name=os.path.basename(object_name),
    display_name=os.path.basename(object_name),
    file_size_bytes=file_size,
    s3_url=s3_uri,
    mime_type="audio/mpeg",
    folder_id=output_folder_id,
    source="generated" # Nguồn gốc sinh thoại tự động
)
db.add(asset)
db.commit()
```

Nhờ cơ chế này:
- File thoại ngay lập tức xuất hiện trong **Thư viện tài nguyên (Asset Library UI)** trên Admin Panel.
- Thừa hưởng 100% cơ chế **Cascade Delete & Hard Delete**: Khi người dùng xóa tệp trên UI, hệ thống sẽ tự động gọi API MinIO xóa tệp vật lý trên S3 để giải phóng dung lượng đĩa cứng mà không để lại file rác.

---

## 🛠️ 5. Hướng Dẫn Vận Hành & Khắc Phục Sự Cố (Ops Guide)

### Cách xem log hoạt động của Worker TTS
Nếu chạy qua script `./dev.sh`, log của Worker TTS sẽ xuất trực tiếp ra màn hình shell chung. Bạn có thể lọc riêng log bằng cách chạy Celery độc lập để debug:

```bash
# Kích hoạt môi trường ảo
source worker_tts/venv/bin/activate

# Chạy Celery worker của TTS ở chế độ debug log
celery -A celery_worker worker -P solo -Q tts_queue --loglevel=info
```

### Lỗi Thường Gặp & Cách Xử Lý (Troubleshooting)

1. **Lỗi không kết nối được MeloTTS (`Could not connect to MeloTTS API`)**:
   - *Triệu chứng*: Log báo lỗi kết nối `http://127.0.0.1:8000` hoặc timeout.
   - *Khắc phục*: Kiểm tra xem dịch vụ MeloTTS API đã chạy chưa bằng lệnh: `curl http://127.0.0.1:8000/health`. Nếu chưa chạy, hãy khởi động MeloTTS API server local. Nếu chạy trên Docker, đảm bảo đã truyền biến cấu hình `TTS_API_URL=http://host.docker.internal:8000`.

2. **Lỗi Edge-TTS bị nghẽn (`Edge-TTS generation failed`)**:
   - *Triệu chứng*: Lỗi phân giải DNS hoặc timeout do mất kết nối mạng Internet.
   - *Khắc phục*: Kiểm tra đường truyền internet từ máy local/WSL. Nếu mạng local chập chờn, hãy chuyển cấu hình `"model": "melotts"` để chạy hoàn toàn offline không cần internet.
