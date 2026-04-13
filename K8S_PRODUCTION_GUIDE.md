# Production Deployment Guide

## Architecture Overview

```
                          ┌─────────────────────────────┐
                          │   Load Balancer / Ingress   │
                          │  (nginx-ingress controller) │
                          └─────────────┬───────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
        ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
        │  Frontend Service   │  │   API Service       │  │  MinIO Console (9001)│
        │  (React)            │  │  (FastAPI - 8000)   │  │                      │
        │  Deployment x2      │  │  Deployment x2-10   │  │  StatefulSet x1      │
        │  port: 80           │  │  port: 8000         │  │  port: 9001          │
        └─────────────────────┘  └─────────────────────┘  └──────────────────────┘
                    │                   │
                    └───────────────────┼───────────────────┐
                                        │                   │
                        ┌───────────────────────┐  ┌────────────────────────┐
                        │   Shared Services     │  │  Worker Deployments    │
                        ├───────────────────────┤  ├────────────────────────┤
                        │ PostgreSQL (port 5432)│  │ • worker-review x1     │
                        │ StatefulSet x1        │  │ • worker-unbox x1      │
                        │                       │  │ • worker-slideshow x1  │
                        │ Redis (port 6379)     │  │ • worker-download x1   │
                        │ Deployment x1         │  │ • worker-promotion x1  │
                        │                       │  │                        │
                        │ MinIO (port 9000)     │  │ Each scales with HPA   │
                        │ StatefulSet x1        │  └────────────────────────┘
                        └───────────────────────┘
                                        │
                        ┌────────────────────────────┐
                        │  Persistent Volumes        │
                        ├────────────────────────────┤
                        │ • postgres-pvc (10Gi)      │
                        │ • minio-pvc (50Gi)         │
                        │ • models-pvc (30Gi)        │
                        └────────────────────────────┘
```

## Deployment Strategies

### 1. Local Development (Minikube)

```bash
# Start Minikube
minikube start --cpus 4 --memory 8192 --disk-size 50g

# Build and load images
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .
docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest .
minikube image load marketing-video-agent:latest
minikube image load marketing-video-agent-frontend:latest

# Deploy
kubectl apply -k k8s/

# Access via port-forward
kubectl port-forward -n video-creator svc/api 8000:8000
kubectl port-forward -n video-creator svc/frontend 3000:80
```

### 2. AWS EKS Production

```bash
# Create cluster
eksctl create cluster --name video-creator --node-type t3.medium --nodes 3

# Setup OIDC provider and storage
eksctl utils associate-iam-oidc-provider --cluster video-creator --approve
eksctl create addon --name aws-ebs-csi-driver --cluster video-creator --service-account-role-arn arn:aws:iam::ACCOUNT_ID:role/AmazonEKS_EBS_CSI_Driver_Role

# Build and push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker build -f admin-api/Dockerfile -t ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/marketing-video-agent:latest .
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/marketing-video-agent:latest

# Update image in k8s/api-deployment.yaml
# Then deploy
kubectl apply -k k8s/

# Setup Ingress with ALB
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller --namespace kube-system
```

### 3. GCP GKE

```bash
# Create cluster
gcloud container clusters create video-creator --zone us-central1-a --num-nodes 3

# Configure kubectl
gcloud container clusters get-credentials video-creator --zone us-central1-a

# Push to GCR
docker build -f admin-api/Dockerfile -t gcr.io/PROJECT_ID/marketing-video-agent:latest .
docker push gcr.io/PROJECT_ID/marketing-video-agent:latest

# Deploy
kubectl apply -k k8s/
```

## High Availability Setup

### 1. Database Replication
```yaml
# PostgreSQL HA with pgBackRest
postgresql:
  primary:
    replicationMode: streaming
  replicas: 2
  backup:
    enabled: true
    schedule: "0 2 * * *"
```

### 2. Redis Sentinel
```yaml
# Redis Sentinel for HA
redis:
  sentinel:
    enabled: true
    replicas: 3
  master:
    replicas: 1
  replica:
    replicas: 2
```

### 3. Multi-zone Deployment
```bash
kubectl apply -f - <<EOF
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
  namespace: video-creator
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app: api
EOF
```

### 4. Horizontal Pod Autoscaler
```bash
# API autoscaling
kubectl autoscale deployment api --min=2 --max=10 --cpu-percent=70 -n video-creator

# Worker autoscaling
kubectl autoscale deployment worker-review --min=1 --max=5 --cpu-percent=80 -n video-creator
```

## Monitoring & Observability

### Prometheus + Grafana
```bash
# Install kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack -n monitoring --create-namespace

# Access Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# User: admin, Password: prom-operator
```

### Centralized Logging (ELK Stack)
```bash
# Install Elasticsearch
helm repo add elastic https://helm.elastic.co
helm install elasticsearch elastic/elasticsearch -n logging --create-namespace

# Install Logstash
helm install logstash elastic/logstash -n logging

# Install Kibana
helm install kibana elastic/kibana -n logging
```

### Application Metrics
Add Prometheus annotations to pods:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

## Backup & Disaster Recovery

### 1. Database Backup
```bash
# Create backup policy
kubectl apply -f - <<EOF
apiVersion: velero.io/v1
kind: Schedule
metadata:
  namespace: velero
  name: daily-backup
spec:
  schedule: "0 2 * * *"
  template:
    ttl: 720h
    includedNamespaces:
    - video-creator
EOF
```

### 2. MinIO Backup (S3-compatible)
```bash
# Enable versioning in MinIO
mc version enable minio/videos

# Setup replication to backup bucket
mc replicate add minio/videos aws-secondary/videos --priority 1
```

### 3. Velero Backup
```bash
# Install Velero
helm repo add vmware-tanzu https://helm.vmware.com/velero
helm install velero vmware-tanzu/velero -n velero --create-namespace

# Create backup
velero backup create video-creator-$(date +%Y%m%d)

# List backups
velero backup get

# Restore
velero restore create --from-backup video-creator-20240415
```

## Security Best Practices

### 1. Network Policies
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: video-creator
spec:
  podSelector: {}
  policyTypes:
  - Ingress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-api-from-ingress
  namespace: video-creator
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
```

### 2. Pod Security Policies
```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: restricted
spec:
  privileged: false
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL
  runAsUser:
    rule: MustRunAsNonRoot
  seLinux:
    rule: MustRunAs
  fsGroup:
    rule: MustRunAs
```

### 3. RBAC Setup
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: video-creator
  name: app-role
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-rolebinding
  namespace: video-creator
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: app-role
subjects:
- kind: ServiceAccount
  name: default
  namespace: video-creator
```

### 4. Secrets Management
```bash
# Using Sealed Secrets
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.18.0/controller.yaml

# Seal a secret
echo -n mypassword | kubectl create secret generic mysecret --dry-run=client --from-file=/dev/stdin -o yaml | kubeseal -f -
```

## Cost Optimization

### 1. Resource Requests/Limits
Set appropriate values to avoid over-provisioning:
```yaml
resources:
  requests:
    cpu: 250m      # Guaranteed allocation
    memory: 256Mi
  limits:
    cpu: 500m      # Max usage
    memory: 512Mi
```

### 2. Pod Disruption Budget
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: api-pdb
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app: api
```

### 3. Reserved Instances / Commitments
- AWS: Use Reserved Instances or Savings Plans
- GCP: Use Committed Use Discounts
- Azure: Use Reserved Instances

## Troubleshooting Guide

### Issue: Apps can't connect to PostgreSQL
```bash
# Check connectivity
kubectl exec -it -n video-creator <pod-name> -- nc -zv postgres 5432

# Check pod logs
kubectl logs -f -n video-creator <pod-name>

# Check service
kubectl get svc postgres -n video-creator
```

### Issue: PVC stuck in Pending
```bash
# Check StorageClass
kubectl get storageclass

# Create a simple PVC to test
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-pvc
  namespace: video-creator
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
EOF
```

### Issue: High memory usage
```bash
# Check pod memory
kubectl top pods -n video-creator

# Check node memory
kubectl top nodes

# Increase limits or add nodes
```

## Compliance & Audit

### 1. Enable Audit Logging
```bash
# On API server, enable audit logging
--audit-log-path=/var/log/audit.log
--audit-policy-file=/etc/kubernetes/audit-policy.yaml
```

### 2. Pod Security Standards
```bash
# Label namespace for Pod Security Standards
kubectl label namespace video-creator pod-security.kubernetes.io/enforce=restricted
```

### 3. RBAC Audit
```bash
# View role bindings
kubectl get rolebindings -n video-creator
kubectl get clusterrolebindings

# Test permissions
kubectl auth can-i list pods --as=system:serviceaccount:video-creator:default
```

---

## Checklist for Production

- [ ] Set resource requests/limits for all pods
- [ ] Configure health checks (liveness/readiness probes)
- [ ] Setup monitoring (Prometheus + Grafana)
- [ ] Configure centralized logging (ELK/Loki)
- [ ] Enable pod disruption budgets
- [ ] Setup network policies
- [ ] Implement RBAC
- [ ] Use sealed secrets for sensitive data
- [ ] Configure backup strategy (Velero)
- [ ] Setup ingress with TLS (cert-manager)
- [ ] Test failover procedures
- [ ] Document runbooks
- [ ] Setup alerts and notifications
- [ ] Plan capacity and scaling strategy
- [ ] Conduct security audit

---

**Need help?** Check the logs: `kubectl logs -f -n video-creator <pod-name>`
