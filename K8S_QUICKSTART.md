# Kubernetes Setup - Quick Start

## 🚀 5-Minute Quick Start

### Prerequisites
```bash
# macOS
brew install kubectl minikube
minikube start --cpus 4 --memory 8192 --disk-size 50g

# Verify
minikube status
```

### Build Images
```bash
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .
docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest .

# Load to Minikube
minikube image load marketing-video-agent:latest
minikube image load marketing-video-agent-frontend:latest
```

### Deploy
```bash
# Option 1: Using script (recommended)
bash setup-k8s-local.sh

# Option 2: Manual
kubectl apply -k k8s/
```

### Access
```bash
# In one terminal
kubectl port-forward -n video-creator svc/api 8000:8000

# In another terminal
kubectl port-forward -n video-creator svc/frontend 3000:80

# Then visit
# - API: http://localhost:8000/docs
# - Frontend: http://localhost:3000
```

---

## 📊 File Structure

```
k8s/
├── namespace.yaml              # Namespace: video-creator
├── configmap.yaml              # Non-sensitive env vars
├── secret.yaml                 # Sensitive data (passwords)
├── pvc.yaml                    # Storage claims
├── postgresql-statefulset.yaml # Database
├── redis-deployment.yaml       # Cache
├── minio-statefulset.yaml      # Object storage
├── api-deployment.yaml         # FastAPI
├── worker-deployments.yaml     # Celery workers (5 workers)
├── frontend-deployment.yaml    # React UI
├── ingress.yaml                # HTTP routing
└── kustomization.yaml          # Kustomize config
```

---

## 📋 Key Changes from Docker Compose

| Aspect | Docker Compose | Kubernetes |
|--------|---|---|
| **Config** | env files | ConfigMap + Secret |
| **Storage** | docker volumes | PersistentVolumeClaim |
| **Networking** | internal DNS | Service + Ingress |
| **Scaling** | manual docker-compose up | kubectl scale deployment |
| **Updates** | docker-compose pull && up | kubectl rollout restart |
| **Definitions** | docker-compose.yml | Multiple YAML files |

---

## 🔧 Common Tasks

### View Logs
```bash
# Single pod
kubectl logs -n video-creator pod/api-xxx

# All API pods
kubectl logs -f -n video-creator -l app=api

# Previous pod (if crashed)
kubectl logs -n video-creator pod/api-xxx --previous
```

### Scale Deployment
```bash
kubectl scale deployment api --replicas=5 -n video-creator
kubectl scale deployment worker-review --replicas=3 -n video-creator
```

### Update Configuration
```bash
# Edit ConfigMap
kubectl edit configmap video-config -n video-creator

# Edit Secret
kubectl edit secret video-secrets -n video-creator

# Restart pods to apply changes
kubectl rollout restart deployment/api -n video-creator
```

### Port Forward
```bash
# API
kubectl port-forward -n video-creator svc/api 8000:8000

# Frontend
kubectl port-forward -n video-creator svc/frontend 3000:80

# Database
kubectl port-forward -n video-creator svc/postgres 5432:5432

# Redis
kubectl port-forward -n video-creator svc/redis 6379:6379

# MinIO
kubectl port-forward -n video-creator svc/minio 9000:9000 9001:9001
```

### Execute Command in Pod
```bash
kubectl exec -it -n video-creator <pod-name> -- /bin/bash
```

### Check Resource Usage
```bash
kubectl top pods -n video-creator
kubectl top nodes
```

---

## 🔍 Debugging

### Check Pod Status
```bash
kubectl describe pod <pod-name> -n video-creator
```

### Check Events
```bash
kubectl get events -n video-creator --sort-by='.lastTimestamp'
```

### Logs with Timestamps
```bash
kubectl logs -f -n video-creator <pod-name> --timestamps=true
```

---

## 📈 Production Checklist

- [ ] **Auth**: Use imagePullSecrets for private registries
- [ ] **Secrets**: Use sealed-secrets or external-secrets operator
- [ ] **Resources**: Set proper CPU/memory requests and limits
- [ ] **Health Checks**: Add liveness and readiness probes
- [ ] **Ingress**: Configure TLS with cert-manager
- [ ] **Monitoring**: Install Prometheus and Grafana
- [ ] **Logging**: Setup ELK or Loki for centralized logging
- [ ] **Backup**: Configure backup for databases
- [ ] **RBAC**: Implement role-based access control
- [ ] **Network Policies**: Restrict pod-to-pod communication
- [ ] **Pod Disruption Budget**: Maintain availability during upgrades
- [ ] **Resource Quotas**: Limit namespace resource consumption

---

## 🚀 Scaling Up

### Horizontal Pod Autoscaler (HPA)
```bash
kubectl autoscale deployment api --min=2 --max=10 --cpu-percent=70 -n video-creator
```

### Vertical Scaling
```bash
# Increase replicas manually
kubectl scale deployment api --replicas=3 -n video-creator
```

---

## 📚 Next Steps

1. **Helm** - Use Helm for templating and reusability
2. **ArgoCD** - GitOps continuous deployment
3. **Monitoring** - Prometheus + Grafana stack
4. **Logging** - ELK Stack or Loki
5. **Service Mesh** - Istio for advanced networking

---

## 📖 Resources

- [Kubernetes Official Docs](https://kubernetes.io/)
- [Kustomize Guide](https://kustomize.io/)
- [Best Practices](https://kubernetes.io/docs/concepts/cluster-administration/manage-deployment/)

---

## ❓ Troubleshooting

### Pod Stuck in `Pending`
```bash
# Check what's wrong
kubectl describe pod <pod-name> -n video-creator

# Usually: not enough resources, volume not available
# Solution: Check node resources, PVC status
```

### Pod in `CrashLoopBackOff`
```bash
# Check logs
kubectl logs -n video-creator <pod-name> --previous

# Usually: wrong env vars, connectivity issues
# Solution: Check ConfigMap, Secret, connectivity to PostgreSQL/Redis
```

### PVC Not Bound
```bash
kubectl describe pvc <pvc-name> -n video-creator

# Usually: no StorageClass or no PV available
# Solution: kubectl get storageclass, or create PV manually
```

---

## 🎯 Quick Reference Commands

```bash
# See everything
kubectl get all -n video-creator

# See just pods and their status
kubectl get pods -n video-creator

# See services and IPs
kubectl get svc -n video-creator

# See persistent volumes
kubectl get pvc -n video-creator

# Watch pods in real-time
kubectl get pods -n video-creator -w

# Get detailed info about a pod
kubectl describe pod <pod-name> -n video-creator

# View pod logs
kubectl logs -f -n video-creator <pod-name>

# Execute in pod
kubectl exec -it -n video-creator <pod-name> -- /bin/bash

# Port forward
kubectl port-forward -n video-creator svc/<service-name> <local>:<remote>

# Scale a deployment
kubectl scale deployment <name> --replicas=<count> -n video-creator

# Restart deployment
kubectl rollout restart deployment/<name> -n video-creator

# Check rollout status
kubectl rollout status deployment/<name> -n video-creator

# View resource usage
kubectl top pods -n video-creator

# Delete all resources
kubectl delete namespace video-creator
```

---

**Start with:** `bash setup-k8s-local.sh` 🚀
