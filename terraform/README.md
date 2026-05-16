# Terraform K8s Configuration

Quản lý Kubernetes resources bằng Terraform cho Marketing Video Agent.

## 📋 Yêu cầu

- Terraform >= 1.0
- kubectl
- Docker (hoặc Docker Desktop)
- Kubernetes cluster (Docker Desktop, Minikube, etc.)

## 📁 Cấu trúc thư mục

```
terraform/
├── main.tf              # Provider và cấu hình cơ bản
├── variables.tf         # Biến đầu vào
├── outputs.tf          # Kết quả đầu ra
├── docker.tf           # Docker image building
├── kubernetes.tf       # K8s resources
├── terraform.tfvars    # Giá trị mặc định
└── README.md           # File này
```

## 🚀 Cách sử dụng

### 1. Khởi tạo Terraform

```bash
cd terraform
terraform init
```

### 2. Kiểm tra kế hoạch deployment

```bash
terraform plan
```

### 3. Deploy lên K8s

```bash
terraform apply
```

Nhập `yes` khi được hỏi để xác nhận.

### 4. Hiển thị outputs

```bash
terraform output
```

## 🔧 Cấu hình

Chỉnh sửa `terraform.tfvars` để thay đổi:

| Tham số | Mô tả | Mặc định |
|---------|-------|---------|
| `namespace` | Kubernetes namespace | `video-creator` |
| `api_replicas` | Số replicas của API | `1` |
| `worker_*_replicas` | Số replicas của workers | `1` |
| `postgres_password` | PostgreSQL password | `postgres_123` |
| `minio_root_password` | MinIO password | `minioadmin` |
| `kubernetes_context` | K8s context | `docker-desktop` |

## 📊 Các resources được tạo

- **Namespace**: `video-creator`
- **ConfigMap**: App configuration
- **Secret**: Sensitive data (passwords)
- **Deployments**:
  - `api` - FastAPI backend
  - `frontend` - React frontend
  - `worker-review`, `worker-research`, `worker-slideshow`, `worker-promotion`, `worker-download` - Celery workers
- **StatefulSets**:
  - `postgresql` - Database
  - `minio` - Object storage
- **Deployment**: `redis` - Cache
- **PersistentVolumeClaims**: Storage cho databases
- **Services**: LoadBalancer cho API và frontend

## 🔗 Port-Forward

```bash
# API
kubectl port-forward -n video-creator svc/api 9100:9100

# Frontend
kubectl port-forward -n video-creator svc/frontend 3000:80

# MinIO
kubectl port-forward -n video-creator svc/minio 9000:9000
```

Sau đó truy cập:
- **API**: http://localhost:9100/docs
- **Frontend**: http://localhost:3000
- **MinIO**: http://localhost:9000

## 📝 Thao tác thường gặp

### Scale API

```bash
terraform apply -var="api_replicas=3"
```

### Xem trạng thái hiện tại

```bash
terraform show
```

### Xem Terraform state

```bash
terraform state list
terraform state show kubernetes_deployment.api
```

### Xóa tất cả resources

```bash
terraform destroy
```

Nhập `yes` để xác nhận.

### Cập nhật một biến

```bash
terraform apply -var="worker_review_replicas=2"
```

## 🐛 Troubleshooting

### Error: Provider test failed

```bash
# Xóa Terraform lock file và khởi tạo lại
rm -rf .terraform* 
terraform init
```

### Error: Image not found

```bash
# Build Docker images trước
docker build -f ../admin-api/Dockerfile -t marketing-video-agent:latest ..
docker build -f ../frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest ..
```

### Pods không chạy

```bash
# Kiểm tra logs
kubectl logs -n video-creator -l app=api

# Kiểm tra status
kubectl get pods -n video-creator
```

## 📚 Tài liệu tham khảo

- [Terraform Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest)
- [Terraform Docker Provider](https://registry.terraform.io/providers/kreuzwerker/docker/latest)
