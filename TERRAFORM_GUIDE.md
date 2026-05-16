# Terraform K8s Deployment Guide

Hướng dẫn chi tiết cách sử dụng Terraform để quản lý Kubernetes resources.

## 🚀 Quick Start

### 1-2 Dòng lệnh để setup hoàn toàn:

```bash
# Installterraform (nếu chưa có)
# macOS: brew install terraform
# Linux: https://www.terraform.io/downloads

# Chạy script all-in-one
bash k8s-terraform-start.sh
```

Script này sẽ:
- ✅ Kiểm tra Docker, kubectl, Terraform
- ✅ Build Docker images
- ✅ Khởi tạo Terraform
- ✅ Hiển thị plan
- ✅ Deploy K8s resources
- ✅ Chờ pods ready

## 📋 Yêu cầu

| Tool | Phiên bản | Cài đặt |
|------|----------|--------|
| Terraform | >= 1.0 | [terraform.io/downloads](https://www.terraform.io/downloads) |
| kubectl | >= 1.20 | `brew install kubectl` |
| Docker | >= 20.0 | [Docker Desktop](https://www.docker.com/products/docker-desktop) |
| Kubernetes | active | Docker Desktop → Settings → Kubernetes → Enable |

## 📁 Cấu trúc Terraform

```
terraform/
├── main.tf              # Provider + Namespaces
├── variables.tf         # Input biến
├── outputs.tf          # Output values
├── docker.tf           # Docker image build
├── kubernetes.tf       # K8s resources
├── terraform.tfvars    # Default values
└── README.md           # Terraform README
```

### File chính

**main.tf** - Cấu hình provider và namespace
```hcl
provider "kubernetes" {
  config_path    = var.kubernetes_config_path
  config_context = var.kubernetes_context
}
```

**docker.tf** - Build Docker images tự động
```hcl
resource "docker_image" "api" {
  name = var.api_image
  build {
    context = "${path.root}/.."
    dockerfile = "../admin-api/Dockerfile"
  }
}
```

**kubernetes.tf** - Tất cả K8s resources
- StatefulSets: PostgreSQL, MinIO
- Deployments: API, Frontend, Workers (5 loại)
- Services: LoadBalancer cho API, Frontend
- ConfigMaps: Environment variables
- Secrets: Passwords & tokens
- PVCs: Storage

## 🎯 Các bước chạy

### Bước 1: Khởi tạo Terraform

```bash
cd terraform
terraform init
```

Output:
```
Initializing the backend...
Initializing provider plugins...
Terraform has been successfully configured!
```

### Bước 2: Xem kế hoạch deployment

```bash
terraform plan
```

Output hiển thị tất cả resources sẽ được tạo:
```
Terraform will perform the following actions:

  # kubernetes_namespace.video_creator will be created
  + resource "kubernetes_namespace" "video_creator" {
      + id = (known after apply)
      ...
    }

Plan: 15 to add, 0 to change, 0 to destroy.
```

### Bước 3: Deploy

```bash
terraform apply
```

Nhập `yes` để xác nhận:
```
Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value: yes
```

### Bước 4: Kiểm tra trạng thái

```bash
terraform show
terraform output
kubectl get all -n video-creator
```

## 🔧 Cấu hình & Tùy chỉnh

### File: terraform.tfvars

Chỉnh sửa các giá trị mặc định:

```hcl
# Replicas
api_replicas               = 1
worker_review_replicas    = 1

# Passwords
database_password = "your-secure-password"
minio_root_password = "your-minio-password"

# Storage
postgres_storage = "10Gi"
minio_storage    = "20Gi"
```

### Các biến có sẵn

| Biến | Mô tả | Mặc định |
|------|-------|---------|
| `namespace` | K8s namespace | `video-creator` |
| `api_replicas` | API instances | `1` |
| `worker_*_replicas` | Worker instances | `1` |
| `api_cpu_request` | API CPU yêu cầu | `100m` |
| `api_memory_request` | API RAM yêu cầu | `256Mi` |
| `postgres_storage` | Database size | `10Gi` |
| `minio_storage` | Storage size | `20Gi` |

## 📊 Ví dụ - Scale API

### Mở rộng API thành 3 instances:

```bash
# Cách 1: Sửa terraform.tfvars
# api_replicas = 3
terraform apply

# Cách 2: Dùng -var flag
terraform apply -var="api_replicas=3"
```

### Mở rộng tất cả workers:

```bash
terraform apply \
  -var="worker_review_replicas=2" \
  -var="worker_research_replicas=2" \
  -var="worker_slideshow_replicas=2" \
  -var="worker_promotion_replicas=2" \
  -var="worker_download_replicas=2"
```

## 🔍 Kiểm tra trạng thái

### Xem tất cả resources trong state

```bash
terraform state list
```

Output:
```
docker_image.api
docker_image.frontend
kubernetes_config_map.app_config
kubernetes_deployment.api
kubernetes_deployment.frontend
kubernetes_deployment.worker_review
...
```

### Xem chi tiết một resource

```bash
terraform state show kubernetes_deployment.api
```

Output:
```
# kubernetes_deployment.api:
resource "kubernetes_deployment" "api" {
  id        = "video-creator/api"
  namespace = "video-creator"
  spec {
    replicas = 1
    ...
  }
}
```

## 🔄 Cập nhật & Rollback

### Cập nhật cấu hình

```bash
# Sửa terraform.tfvars
nano terraform.tfvars

# Xem thay đổi
terraform plan

# Áp dụng
terraform apply
```

### Rollback về phiên bản trước

```bash
# Xem lịch sử state
terraform state list

# Reload state từ backup
terraform state pull > backup.tfstate
```

## 🗑️ Xóa tất cả resources

```bash
terraform destroy
```

Nhập `yes` để xác nhận:
```
Do you really want to destroy all resources?
  Terraform will destroy all your managed infrastructure.
  
  Enter a value: yes
```

Nó sẽ xóa:
- Namespace
- Deployments
- StatefulSets
- Services
- ConfigMaps
- Secrets
- PVCs

## 🐛 Troubleshooting

### Error: Provider version constraint

```bash
rm -rf .terraform*
terraform init
```

### Error: Image not found

```bash
# Build images trước
docker build -f ../admin-api/Dockerfile -t marketing-video-agent:latest ..
docker build -f ../frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest ..

# Rồi chạy lại
terraform apply
```

### Pods không chạy

```bash
# Kiểm tra logs
kubectl logs -n video-creator -l app=api

# Kiểm tra events
kubectl describe pod -n video-creator <pod-name>

# Xem status
kubectl get pods -n video-creator -o wide
```

### State file bị lock

```bash
# Force unlock (cẩn thận!)
terraform force-unlock <lock-id>
```

## 🔗 Port-Forward

```bash
# API (9100)
kubectl port-forward -n video-creator svc/api 9100:9100

# Frontend (3000)
kubectl port-forward -n video-creator svc/frontend 3000:80

# MinIO (9000)
kubectl port-forward -n video-creator svc/minio 9000:9000
```

Access:
- **API**: http://localhost:9100/docs
- **Frontend**: http://localhost:3000
- **MinIO**: http://localhost:9000

## 📚 Tài liệu tham khảo

- [Terraform Documentation](https://www.terraform.io/docs)
- [Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest)
- [Docker Provider](https://registry.terraform.io/providers/kreuzwerker/docker/latest)
- [Terraform Best Practices](https://terraform.io/cloud-docs/recommended-practices)

## 🎓 Học thêm

### Terraform Basics

```bash
# Kiểm tra syntax
terraform validate

# Format code
terraform fmt

# Validate cấu hình
terraform plan -out=tfplan

# Dry-run
terraform plan -destroy
```

### Advanced

```bash
# Tạo workspace cho environment khác
terraform workspace new production
terraform workspace select production

# Import resource tồn tại
terraform import kubernetes_deployment.api video-creator/api

# Taint resource (buộc rebuild)
terraform taint kubernetes_deployment.api
terraform apply
```

## 🤝 Đóng góp

Để báo cáo bug hoặc đề xuất cải tiến, hãy tạo issue trong repository.
