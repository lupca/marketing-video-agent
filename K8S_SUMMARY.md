# Kubernetes Migration - Summary

## ✅ Tất cả files đã được tạo thành công!

### 📁 Cấu trúc thư mục K8s

```
k8s/
├── namespace.yaml                    # Namespace: video-creator
├── configmap.yaml                    # Configuration (non-sensitive)
├── secret.yaml                       # Secrets (passwords, keys)
├── pvc.yaml                          # Persistent Volumes (DB, MinIO, models)
├── postgresql-statefulset.yaml       # PostgreSQL Database
├── redis-deployment.yaml             # Redis Cache
├── minio-statefulset.yaml            # MinIO Object Storage
├── api-deployment.yaml               # FastAPI Admin API
├── worker-deployments.yaml           # 5 Celery Workers
├── frontend-deployment.yaml          # React Frontend
├── ingress.yaml                      # HTTP/HTTPS Routing
└── kustomization.yaml                # Kustomize Configuration
```

### 📚 Tài liệu đã tạo

1. **K8S_MIGRATION_GUIDE.md** - Chi tiết từng bước chuyển từ Docker Compose sang K8s
2. **K8S_QUICKSTART.md** - Hướng dẫn nhanh bắt đầu trong 5 phút
3. **K8S_PRODUCTION_GUIDE.md** - Hướng dẫn deploy production, monitoring, backup, security

### 🚀 Công cụ hỗ trợ

1. **deploy-k8s.sh** - Script deploy tự động (chọn local/aws/gcp/azure)
2. **setup-k8s-local.sh** - Script setup nhanh cho local development với Minikube
3. **Dockerfile.k8s** - Dockerfile cho build image duy nhất chứa cả API và workers
4. **helm-values.yaml** - Configuration cho Helm deployment (tương lai)

---

## 🎯 Bắt đầu ngay

### Option 1: Quick Start (5 phút)

```bash
# 1. Cài đặt prerequisites (nếu chưa có)
# macOS:
brew install docker minikube kubectl

# 2. Start Minikube
minikube start --cpus 4 --memory 8192 --disk-size 50g

# 3. Deploy (tự động build, load, deploy)
bash setup-k8s-local.sh

# 4. Truy cập
kubectl port-forward -n video-creator svc/api 8000:8000
# -> API: http://localhost:8000/docs
```

### Option 2: Manual Deploy

```bash
# Build images
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .
docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest .

# Load to Minikube
minikube image load marketing-video-agent:latest
minikube image load marketing-video-agent-frontend:latest

# Deploy
kubectl apply -k k8s/

# Check status
kubectl get pods -n video-creator -w
```

### Option 3: Custom Deploy

```bash
# Chỉ deploy từng component
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/postgresql-statefulset.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/minio-statefulset.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployments.yaml
kubectl apply -f k8s/frontend-deployment.yaml
```

---

## 📖 Tài liệu tham khảo

### Quick Reference

| Tác vụ | Lệnh |
|--------|------|
| Xem tất cả pods | `kubectl get pods -n video-creator` |
| Xem logs | `kubectl logs -f -n video-creator <pod-name>` |
| Port forward | `kubectl port-forward -n video-creator svc/api 8000:8000` |
| Scale deployment | `kubectl scale deployment api --replicas=5 -n video-creator` |
| Restart pods | `kubectl rollout restart deployment/api -n video-creator` |
| Exec vào pod | `kubectl exec -it -n video-creator <pod-name> -- /bin/bash` |
| Xem metrics | `kubectl top pods -n video-creator` |
| Delete namespace | `kubectl delete namespace video-creator` |

### Các file nên đọc

1. **Bắt đầu:** K8S_QUICKSTART.md
2. **Chi tiết:** K8S_MIGRATION_GUIDE.md
3. **Production:** K8S_PRODUCTION_GUIDE.md

---

## 🔄 So sánh: Docker Compose vs Kubernetes

### Docker Compose (Cũ)
```bash
docker-compose up -d
docker-compose logs -f
docker-compose down
```

### Kubernetes (Mới)
```bash
kubectl apply -k k8s/
kubectl logs -f -n video-creator <pod-name>
kubectl delete namespace video-creator
```

**Lợi ích K8s:**
- ✅ Multi-host orchestration
- ✅ Auto-scaling (HPA)
- ✅ Self-healing
- ✅ Rolling updates
- ✅ Service discovery
- ✅ Load balancing
- ✅ Storage management
- ✅ Monitoring & logging

---

## 🚀 Scaling & High Availability

### Horizontal Scaling (Thêm replicas)
```bash
# Scale API to 5 instances
kubectl scale deployment api --replicas=5 -n video-creator

# Or using Autoscaler
kubectl autoscale deployment api --min=2 --max=10 --cpu-percent=70 -n video-creator
```

### Monitoring
```bash
# Prometheus + Grafana
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring

# Access Grafana: localhost:3000 (admin/prom-operator)
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
```

### Backup
```bash
# Database backup
kubectl exec -it -n video-creator postgres-0 -- \
  pg_dump -U admin video_creator > backup.sql

# Using Velero (backup tool)
helm install velero vmware-tanzu/velero -n velero
velero backup create video-creator-$(date +%Y%m%d)
```

---

## ⚠️ Ghi chú quan trọng

### 1. Image Registry
- **Local development**: Sử dụng local Docker images với Minikube
- **Production**: Push lên registry (Docker Hub, ECR, GCR, etc.)

### 2. Secrets Management
- **Development**: Dùng plain text trong secret.yaml
- **Production**: Dùng Sealed Secrets hoặc External Secrets

### 3. Storage
- **Local**: Minikube storage provisioner
- **Production**: AWS EBS, GCP Persistent Disks, Azure Disks

### 4. Networking
- **Local**: Port forwarding
- **Production**: Ingress with TLS, Load Balancer

---

## 🐛 Troubleshooting

### Pod stuck in Pending?
```bash
kubectl describe pod <pod-name> -n video-creator
# Thường: không có resources, PVC chưa bound
```

### Pod CrashLoopBackOff?
```bash
kubectl logs -n video-creator <pod-name> --previous
# Thường: env vars sai, không connect được database
```

### Database không connect?
```bash
# Port forward và test
kubectl port-forward -n video-creator svc/postgres 5432:5432
psql -h localhost -U admin -d video_creator
```

---

## 📋 Next Steps

1. ✅ Deploy lên local Minikube
2. 🔲 Test tất cả services hoạt động
3. 🔲 Setup monitoring (Prometheus + Grafana)
4. 🔲 Configure backup (Velero)
5. 🔲 Setup CI/CD (ArgoCD, Jenkins)
6. 🔲 Deploy lên production cloud (AWS/GCP/Azure)
7. 🔲 Configure TLS/HTTPS
8. 🔲 Setup alerting

---

## 📞 Hỗ trợ

**Cần giúp?** Đọc lại:
- K8S_QUICKSTART.md - Câu hỏi nhanh
- K8S_MIGRATION_GUIDE.md - Chi tiết từng bước
- K8S_PRODUCTION_GUIDE.md - Production setup

**Xem logs:**
```bash
kubectl logs -f -n video-creator <pod-name>
```

**Describe pod:**
```bash
kubectl describe pod <pod-name> -n video-creator
```

---

## 📊 Metrics & Health

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| API | 8000 | FastAPI |
| Frontend | 80/3000 | React Web UI |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| MinIO | 9000 | Object Storage |
| MinIO Console | 9001 | Management UI |

### ConfigMap & Secret

**ConfigMap** (video-config):
- DATABASE_URL
- REDIS_URL
- MINIO_ENDPOINT
- Model paths (HF_HOME, TORCH_HOME, etc.)

**Secret** (video-secrets):
- POSTGRES_USER/PASSWORD
- MINIO_ACCESS_KEY/SECRET_KEY

---

## ✨ Tính năng chính

✅ PostgreSQL: Persistent data
✅ Redis: Task queue (Celery)
✅ MinIO: Object storage (S3-compatible)
✅ API: FastAPI admin interface
✅ Frontend: React web UI
✅ Workers: 5 Celery workers (review, unbox, slideshow, download, promotion)
✅ Networking: Kubernetes Service + Ingress
✅ Storage: PersistentVolumeClaim

---

**Bắt đầu:** `bash setup-k8s-local.sh` hoặc `bash deploy-k8s.sh local` 🚀

Chúc bạn thành công! 💪
