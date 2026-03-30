# Lộ trình DevOps: Hệ thống Video Creator Platform

Dựa trên kiến trúc xử lý video hiện tại (FastAPI, Postgres, Redis, MinIO, Celery Workers), đây là lộ trình DevOps thực tế, chia thành các giai đoạn từ cơ bản đến nâng cao để đảm bảo hệ thống chạy ổn định, tiết kiệm chi phí và dễ dàng mở rộng (Scale).

---

## Giai đoạn 1: Chuẩn hóa & Tối ưu (Dành cho 1 Server)
*Mục tiêu: Làm cho quá trình deploy hiện tại mượt mà nhất, tốn ít tài nguyên nhất.*

1. **Tối ưu Dockerfile (Tạo Base Image)**
   - Tạo `Dockerfile.base` chứa tất cả thư viện nặng (FFmpeg, PyTorch, OpenCV, v.v.).
   - Các `worker_*` (review, unbox, slideshow) sẽ kế thừa từ `worker-base:latest` để giảm dung lượng Build (như sơ đồ đã thảo luận).

2. **Giới hạn tài nguyên (Resource Constraints)**
   - Cập nhật `docker-compose.yml` định nghĩa rõ `deploy.resources.limits` cho từng worker (CPU/RAM).
   - Ví dụ: `worker_unbox` giới hạn 2 CPU, 4GB RAM để tránh OOM (Out of Memory) làm treo toàn bộ server.

3. **External Volume cho Model AI**
   - Không chứa Model (HuggingFace/Torch cache) bên trong Image.
   - Mount một thư mục ngoại vi (vd: `/mnt/data/models:/models`) để các container worker dùng chung Model, không phải tải lại mỗi lần khởi động.

---

## Giai đoạn 2: Tự động hóa (CI/CD Pipeline)
*Mục tiêu: Không còn gõ lệnh thủ công để deploy. Code đẩy lên Git là server tự cập nhật.*

1. **Continuous Integration (CI) với GitHub Actions / GitLab CI**
   - Viết luồng CI chạy tự động mỗi khi có code Push hoặc Merge Request:
     - Linter & Formatter (flake8, black, isort).
     - Build thử Image xem có lỗi cú pháp Docker không.

2. **Tự động Build & Cung cấp Image (Registry)**
   - Mỗi khi Merge code vào nhánh `main`, CI sẽ tự động build `worker-base` (nếu có đổi ở requirements) và các worker image lẻ.
   - Push các Image này lên một Container Registry (Docker Hub riêng, AWS ECR, hoặc GitHub Container Registry).

3. **Continuous Deployment (CD) Cơ bản**
   - Viết script để Server tự động kéo (`docker-compose pull`) Image mới về và khởi động lại (`docker-compose up -d`) khi có release mới.

---

## Giai đoạn 3: Giám sát & Cảnh báo (Monitoring & Observability)
*Mục tiêu: Biết hệ thống "chết" trước khi bị khách hàng phàn nàn và biết chính xác tắc nghẽn ở đâu.*

1. **Giám sát Hàng đợi (Celery & Redis)**
   - Cài đặt **Flower** (Giao diện web cho Celery) để xem có bao nhiêu Job đang chờ, Job nào thất bại, Worker nào đang chạy.
   - Đặt cảnh báo: Nếu số lượng message trong Redis Queue lớn hơn 50 trong 10 phút -> Gửi tin nhắn qua Telegram/Slack.

2. **Giám sát Server & Container (Hạ tầng)**
   - Triển khai combo **Prometheus + Grafana + cAdvisor**.
   - Mục đích: Xem biểu đồ CPU, RAM, Network I/O, Disk I/O của từng Server và từng Container Worker để đưa ra quyết định mua thêm RAM hay CPU hợp lý.

3. **Quản lý Log tập trung**
   - Không đọc log bằng `docker logs` thủ công nữa. Triển khai **Loki + Promtail** (hoặc ELK stack loại nhẹ) để gom toàn bộ log của các Worker về một màn hình tìm kiếm.

---

## Giai đoạn 4: Kiến trúc Đa Máy Chủ (Multi-Server & Load Balancing)
*Mục tiêu: Đạt sức giới hạn của 1 Server, cần thêm máy để chạy nhiều Worker hơn.*

1. **Phân tách Server Logic**
   - **Server A (Control Plane):** Chạy API, PostgreSQL, Redis, MinIO (hoặc dùng S3/RDS của Cloud).
   - **Server B, C, D (Worker Nodes):** Chỉ chạy các container `worker_unbox`, `worker_slideshow`, v.v.

2. **Mạng nội bộ (VPC / Private Network)**
   - Cấu hình cho Server B, C, D chỉ nói chuyện với Server A qua mạng LAN (VPC) để đảm bảo tốc độ tải file video cực nhanh từ MinIO và bảo mật Database.

3. **Giải quyết tình trạng nghẽn Database**
   - Cài đặt **PgBouncer** trước PostgreSQL trên Server A. Khi số lượng Worker lên đến hàng trăm, PgBouncer sẽ gom kết nối giúp DB không bị sụp.

4. **Công cụ điều phối (Orchestration)**
   - Chuyển `docker-compose` sang sử dụng **Docker Swarm Mode** (Rất khuyên dùng vì dễ học, phù hợp team nhỏ) để quản lý cụm Server.
   - Hoặc dùng **Ansible** để tự động cài đặt và deploy Worker mới lên bất kỳ máy ảo (VPS) nào vừa mới thuê chỉ với 1 cú click.

---

## Giai đoạn 5: Tự động Mở Rộng (Auto-Scaling - Tương lai)
*Mục tiêu: Hệ thống tự động đẻ thêm Worker khi nghẽn và tự tắt đi khi rảnh rỗi để tiết kiệm tiền Cloud.*

- **Kubernetes (K8s) + KEDA:** Khi hệ thống đạt quy mô doanh nghiệp lớn.
  - KEDA sẽ đứng đọc Redis Queue. 
  - Đêm khuya không ai render: Scale worker về 0 (đỡ tốn tiền).
  - Ban ngày có sự kiện, 1000 người render video: KEDA nhận thấy Queue Redis vọt lên -> Ra lệnh thuê thêm máy Cloud -> Bật 50 Worker -> Chạy xong tự tắt máy trả lại Cloud.

---

> **LỜI KHUYÊN CHO HIỆN TẠI TỪ DEVOPS:**
> 1. Khoan vội dùng Kubernetes, nó sẽ "bóp nghẹt" thời gian của bạn.
> 2. Hãy hoàn thành tốt **Giai đoạn 1 và 2** ngay lập tức. Cần tách `Base Image` để code nhẹ đi và dựng CI/CD để không phải copy file thủ công.
> 3. Tiếp theo là dựng **Flower** để nhìn thấy được lượng Job video thực tế đang chạy thế nào.
