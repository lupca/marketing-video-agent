# Kubernetes Migration Guide

## Tổng quan

Tài liệu này hướng dẫn bạn chuyển từ Docker Compose sang Kubernetes (K8s) cho ứng dụng Marketing Video Agent.

## Prerequisites

- Kubernetes cluster (v1.24+). Bạn có thể sử dụng:
  - **Local**: Docker Desktop, Minikube, or Kind
  - **Cloud**: AWS EKS, GCP GKE, Azure AKS
- `kubectl` CLI tool
- `kustomize` hoặc `kubectl apply -k`

## Cấu trúc K8s

```
k8s/
├── namespace.yaml                    # Namespace cho ứng dụng
├── configmap.yaml                    # Non-sensitive environment variables
├── secret.yaml                       # Sensitive data (passwords, keys)
├── pvc.yaml                          # Persistent Volume Claims
├── postgresql-statefulset.yaml       # PostgreSQL database
├── redis-deployment.yaml             # Redis cache
├── minio-statefulset.yaml            # MinIO object storage
├── api-deployment.yaml               # FastAPI admin API
├── worker-deployments.yaml           # Celery workers
├── frontend-deployment.yaml          # React frontend
├── ingress.yaml                      # HTTP routing
├── kustomization.yaml                # Kustomize configuration
└── README.md                         # Tài liệu K8s
```

## Bước 1: Chuẩn bị Cluster

### 1.1 Tạo cluster locally (Minikube)

```bash
minikube start \
  --cpus 4 \
  --memory 8192 \
  --disk-size 50g \
  --driver docker
```

### 1.2 Xác minh cluster

```bash
kubectl cluster-info
kubectl get nodes
```

## Bước 2: Build Docker Images

Bạn cần build 2 Docker images cho K8s:

```bash
# Build API image
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .

# Build frontend image
docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest .

# Nếu sử dụng local registry (Minikube)
minikube image load marketing-video-agent:latest
minikube image load marketing-video-agent-frontend:latest
```

### Hoặc push lên container registry (nếu sử dụng cloud cluster)

```bash
# Docker Hub
docker tag marketing-video-agent:latest username/marketing-video-agent:latest
docker push username/marketing-video-agent:latest

# AWS ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
docker tag marketing-video-agent:latest 123456789.dkr.ecr.us-east-1.amazonaws.com/marketing-video-agent:latest
docker push 123456789.dkr.ecr.us-east-1.amazonaws.com/marketing-video-agent:latest
```

## Bước 3: Deploy lên K8s

### 3.1 Deploy sử dụng Kustomize (Recommended)

```bash
# Apply tất cả resources
kubectl apply -k k8s/

# Hoặc từng file
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/postgresql-statefulset.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/minio-statefulset.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployments.yaml
kubectl apply -f k8s/frontend-deployment.yaml
```

### 3.2 Xác minh deployment

```bash
# Kiểm tra namespace
kubectl get namespace

# Kiểm tra tất cả resources
kubectl get all -n video-creator

# Kiểm tra pods
kubectl get pods -n video-creator -w

# Kiểm tra services
kubectl get svc -n video-creator

# Kiểm tra persistent volumes
kubectl get pvc -n video-creator
```

## Bước 4: Truy cập ứng dụng

### 4.1 Port forwarding (Local development)

```bash
# API
kubectl port-forward -n video-creator svc/api 8000:8000

# Frontend
kubectl port-forward -n video-creator svc/frontend 3000:80

# Redis
kubectl port-forward -n video-creator svc/redis 6379:6379

# PostgreSQL
kubectl port-forward -n video-creator svc/postgres 5432:5432

# MinIO
kubectl port-forward -n video-creator svc/minio 9000:9000 9001:9001
```

Sau đó truy cập:
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000
- MinIO Console: http://localhost:9001

### 4.2 Ingress (Production)

Nếu cluster có Ingress Controller (NGINX Ingress):

```bash
# Install NGINX Ingress (nếu chưa cài)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install nginx-ingress ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace

# Lấy External IP
kubectl get ingress -n video-creator

# Update hosts file hoặc DNS
# api.example.com       -> EXTERNAL_IP
# app.example.com       -> EXTERNAL_IP
# minio.example.com     -> EXTERNAL_IP
```

## Bước 5: Monitoring & Logging

### 5.1 Xem logs

```bash
# Xem logs của một pod
kubectl logs -n video-creator <pod-name>

# Xem logs real-time
kubectl logs -f -n video-creator <pod-name>

# Xem logs tất cả pods của một deployment
kubectl logs -f -n video-creator -l app=api
```

### 5.2 Describe pod (debug)

```bash
kubectl describe pod -n video-creator <pod-name>
```

### 5.3 Exec vào pod

```bash
kubectl exec -it -n video-creator <pod-name> -- /bin/sh
```

## Bước 6: Configuration Management

### 6.1 Cập nhật ConfigMap (non-sensitive config)

```bash
kubectl edit configmap video-config -n video-creator
```

### 6.2 Cập nhật Secret (passwords, keys)

```bash
# Update secret
kubectl edit secret video-secrets -n video-creator

# Hoặc delete và tạo lại
kubectl delete secret video-secrets -n video-creator
kubectl apply -f k8s/secret.yaml
```

Sau khi cập nhật, restart pods:

```bash
kubectl rollout restart deployment/api -n video-creator
kubectl rollout restart deployment/worker-review -n video-creator
# ... etc
```

## Bước 7: Scaling & Performance

### 7.1 Scale deployments

```bash
# Scale API deployment
kubectl scale deployment api --replicas=5 -n video-creator

# Scale workers
kubectl scale deployment worker-review --replicas=3 -n video-creator
```

### 7.2 Horizontal Pod Autoscaler (HPA)

```bash
kubectl autoscale deployment api --min=2 --max=10 --cpu-percent=70 -n video-creator
kubectl autoscale deployment worker-review --min=1 --max=5 --cpu-percent=80 -n video-creator
```

## Bước 8: Backup & Recovery

### 8.1 Backup PostgreSQL

```bash
# Port forward
kubectl port-forward -n video-creator svc/postgres 5432:5432

# Backup
pg_dump -h localhost -U admin -d video_creator > backup.sql

# Restore
psql -h localhost -U admin -d video_creator < backup.sql
```

### 8.2 Backup shared PVC (models)

```bash
kubectl exec -it -n video-creator <pod-name> -- tar czf /tmp/models-backup.tar.gz /models
kubectl cp video-creator/<pod-name>:/tmp/models-backup.tar.gz ./models-backup.tar.gz
```

## Bước 9: Cleanup

```bash
# Delete tất cả resources trong namespace
kubectl delete namespace video-creator

# Hoặc delete từng resource
kubectl delete -k k8s/
```

## Troubleshooting

### Problem: Pod stuck in Pending

```bash
kubectl describe pod <pod-name> -n video-creator
kubectl top nodes  # Check node resources
```

**Solution**: 
- Tăng node resources
- Hoặc reduce resource requests

### Problem: CrashLoopBackOff

```bash
kubectl logs <pod-name> -n video-creator
```

**Solution**:
- Kiểm tra environment variables
- Kiểm tra database/redis connectivity
- Kiểm tra image tag

### Problem: PVC not bound

```bash
kubectl describe pvc <pvc-name> -n video-creator
```

**Solution**:
- Kiểm tra storage class
- Tạo PV manually hoặc cài storage provisioner

## Differences: Docker Compose vs Kubernetes

| Feature | Docker Compose | Kubernetes |
|---------|----------------|-----------|
| Orchestration | Single host | Multi-host |
| Scaling | Manual | Automatic (HPA) |
| Updates | Stop/restart | Rolling updates |
| Networking | Internal DNS | Service mesh |
| Storage | Local volumes | PVC/PV |
| Security | env files | Secrets/RBAC |
| Monitoring | Limited | Prometheus/ELK |
| Cost | Low | Higher (multi-node) |

## Next Steps

1. **Helm** - Templatize configurations
2. **ArgoCD** - GitOps deployment
3. **Prometheus + Grafana** - Monitoring
4. **ELK Stack** - Centralized logging
5. **Service Mesh** (Istio/Linkerd) - Advanced traffic management
6. **RBAC** - Role-based access control
7. **Network Policies** - Security policies

## Resources

- [Kubernetes Official Docs](https://kubernetes.io/docs/)
- [Kustomize Guide](https://kustomize.io/)
- [StatefulSets vs Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)

---

**Chúc bạn thành công với K8s migration!** 🚀
