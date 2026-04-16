# Troubleshooting: Pods Not Ready

Hướng dẫn giải quyết khi pods không được ready với Terraform + K8s.

## ❌ Triệu chứng

```
Error: Waiting for rollout to finish: 1 replicas wanted; 0 replicas Ready
  with kubernetes_deployment.api
```

## 🔍 Kiểm tra nhanh

### 1. Kiểm tra Docker images

```bash
# Liệt kê các image đã build
docker images | grep marketing-video-agent

# Đầu ra dự kiến:
# marketing-video-agent                        latest    sha256:abc123...    2 minutes ago
# marketing-video-agent-frontend               latest    sha256:def456...    1 minute ago
```

Nếu không thấy image, rebuild lại:
```bash
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .
docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest frontend-admin/
```

### 2. Kiểm tra K8s pods

```bash
# Xem status pods
kubectl get pods -n video-creator

# Đầu ra dự kiến:
# NAME                     READY   STATUS    RESTARTS   AGE
# api-xxx                  1/1     Running   0          2m
# frontend-xxx             1/1     Running   0          1m
# postgresql-0             1/1     Running   0          3m
# redis-xxx                1/1     Running   0          2m
# minio-0                  1/1     Running   0          2m
```

### 3. Xem chi tiết pod

```bash
# Xem chi tiết API pod
kubectl describe pod -n video-creator -l app=api

# Tìm section "Status:" và "Events:" ở dưới
# Status sẽ hiển thị tại sao pod không ready
```

### 4. Xem logs

```bash
# Xem logs của API pod
kubectl logs -n video-creator -l app=api

# Nếu pod còn đang khởi tạo:
kubectl logs -n video-creator -l app=api --tail=50

# Xem logs của container cụ thể
kubectl logs -n video-creator <POD_NAME> -c api
```

## 🛠️ Các lỗi phổ biến & cách sửa

### Lỗi 1: ImagePullBackOff

```
Events:
  Type     Reason             Age   Message
  ----     ------             ----  -------
  Normal   Scheduled          1m    ...
  Warning  Failed             1m    Failed to pull image...
```

**Nguyên nhân**: Image không tồn tại trong Docker registry

**Cách sửa**:
```bash
# 1. Build Docker images nếu chưa
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .

# 2. Kiểm tra image tồn tại
docker image inspect marketing-video-agent:latest

# 3. Xóa pod cũ để tạo mới
kubectl delete pods -n video-creator -l app=api
```

### Lỗi 2: CrashLoopBackOff

```
Status: 0/1
  Last State:     Terminated
    Exit Code: 1
```

**Nguyên nhân**: Container crash khi khởi động (lỗi application, missing dependency)

**Cách sửa**:
```bash
# Xem logs để biết lỗi gì
kubectl logs -n video-creator <POD_NAME>

# Ví dụ - nếu thấy "ModuleNotFoundError":
# - Build lại Dockerfile
# - Kiểm tra requirements.txt

# Nếu lỗi liên quan API:
# - PostgreSQL chưa ready
# - Redis chưa ready
# - Environment variables không đúng
```

### Lỗi 3: Pending

```
Status: 0/1
  Phase: Pending
```

**Nguyên nhân**: Pod đang chờ resource hoặc node không đủ tài nguyên

**Cách sửa**:
```bash
# Kiểm tra PVC status
kubectl get pvc -n video-creator

# Nếu PVC pending:
# - Docker Desktop K8s không có dynamic provisioning
# - Cần tạo PV (thường tự tạo)

# Kiểm tra node resources
kubectl top nodes
kubectl top pods -n video-creator

# Nếu node không đủ memory/cpu:
# - Đóng các ứng dụng khác
# - Tăng resources cho Docker Desktop (Settings → Resources)
```

## 🚀 Các lệnh hữu ích

### Restart deployments

```bash
# Restart API
kubectl rollout restart deployment/api -n video-creator

# Restart tất cả
kubectl rollout restart deployment -n video-creator
```

### Scale deployments

```bash
# Scale API xuống 0 rồi lên 1
kubectl scale deployment api --replicas=0 -n video-creator
sleep 5
kubectl scale deployment api --replicas=1 -n video-creator
```

### Debug container

```bash
# Truy cập vào container (nếu pod đang chạy)
kubectl exec -it -n video-creator <POD_NAME> -- /bin/bash

# Hoặc /bin/sh nếu không có bash
kubectl exec -it -n video-creator <POD_NAME> -- /bin/sh
```

### Xem Dockerfile trong Docker

```bash
# Xem history của image (Dockerfile layers)
docker image history marketing-video-agent:latest
```

## 📋 Danh sách kiểm tra

- [ ] Docker Desktop K8s enabled?
  ```bash
  kubectl cluster-info
  ```

- [ ] Docker images built?
  ```bash
  docker images | grep marketing-video-agent
  ```

- [ ] Images có correct tag?
  ```bash
  docker image inspect marketing-video-agent:latest
  ```

- [ ] Pods createdready?
  ```bash
  kubectl get pods -n video-creator
  ```

- [ ] PostgreSQL ready?
  ```bash
  kubectl logs -n video-creator -l app=postgresql
  ```

- [ ] Redis ready?
  ```bash
  kubectl logs -n video-creator -l app=redis
  ```

- [ ] Environment variables set?
  ```bash
  kubectl get cm -n video-creator
  kubectl get secret -n video-creator
  ```

## 🧹 Làm sạch & thử lại

```bash
# Xóa deployment cũ
kubectl delete deployment -n video-creator --all
kubectl delete statefulset -n video-creator --all

# Xóa namespace hoàn toàn
kubectl delete namespace video-creator

# Reapply Terraform
cd terraform
terraform destroy -auto-approve
terraform apply -auto-approve

# Hoặc dùng script
bash k8s-terraform-start.sh
```

## 📞 Chi tiết logs

Khi báo cáo issue, hãy cung cấp:

```bash
# 1. Pod status
kubectl get pods -n video-creator -o wide

# 2. Pod description (tất cả events)
kubectl describe pod -n video-creator -l app=api

# 3. Pod logs
kubectl logs -n video-creator -l app=api --tail=100

# 4. Docker images
docker images | grep marketing-video-agent

# 5. Terraform state
cd terraform && terraform show
```

## 🎯 Nếu vẫn không hoạt động

1. **Kiểm tra Docker Desktop Settings**:
   - Kubernetes tiếp tục enabled?
   - Resources đủ không? (recommend: 4 CPUs, 8GB RAM)

2. **Kiểm tra network**:
   ```bash
   kubectl get svc -n video-creator
   ```

3. **Kiểm tra Dockerfile**:
   - COPY commands đúng path?
   - RUN commands chạy thành công?

4. **Kiểm tra requirements**:
   - Python: requirements.txt có all dependencies?
   - Node: package.json & package-lock.json sync?

5. **Thử build image thủ công**:
   ```bash
   docker build -f admin-api/Dockerfile -t test-api:latest .
   docker run -it --rm test-api:latest /bin/bash
   ```

---

**Tip**: Dùng `watch` command để theo dõi real-time:
```bash
watch kubectl get pods -n video-creator
```

Còn câu hỏi nào không?
