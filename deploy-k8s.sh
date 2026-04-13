#!/bin/bash
# K8s deployment helper script

set -e

NAMESPACE="video-creator"
CLUSTER_TYPE="${1:-local}"  # local, aws, gcp, azure

echo "🚀 Marketing Video Agent - Kubernetes Deployment"
echo "=================================================="
echo "Cluster Type: $CLUSTER_TYPE"
echo "Namespace: $NAMESPACE"
echo ""

# Verify kubectl
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl."
    exit 1
fi

echo "✅ kubectl found"
echo ""

# Step 1: Verify cluster
echo "📋 Step 1: Verifying Kubernetes cluster..."
if kubectl cluster-info &> /dev/null; then
    echo "✅ Kubernetes cluster is accessible"
    kubectl cluster-info | head -3
else
    echo "❌ Cannot connect to Kubernetes cluster"
    echo "Please start your cluster (minikube start, or connect to cloud cluster)"
    exit 1
fi
echo ""

# Step 2: Check if namespace exists
echo "📋 Step 2: Setting up namespace..."
if kubectl get namespace $NAMESPACE &> /dev/null; then
    echo "✅ Namespace '$NAMESPACE' already exists"
else
    echo "📍 Creating namespace '$NAMESPACE'..."
    kubectl create namespace $NAMESPACE
    echo "✅ Namespace created"
fi
echo ""

# Step 3: List available Docker images
echo "📋 Step 3: Checking Docker images..."
API_IMAGE="marketing-video-agent:latest"
FRONTEND_IMAGE="marketing-video-agent-frontend:latest"

if [ "$CLUSTER_TYPE" = "local" ]; then
    echo "🔍 Checking local images with 'docker images'..."
    if docker image inspect $API_IMAGE &> /dev/null; then
        echo "✅ API image found: $API_IMAGE"
    else
        echo "⚠️  API image not found. Please build it:"
        echo "   docker build -f admin-api/Dockerfile -t $API_IMAGE ."
    fi

    if docker image inspect $FRONTEND_IMAGE &> /dev/null; then
        echo "✅ Frontend image found: $FRONTEND_IMAGE"
    else
        echo "⚠️  Frontend image not found. Please build it:"
        echo "   docker build -f frontend-admin/Dockerfile -t $FRONTEND_IMAGE ."
    fi

    # Load images to Minikube if using Minikube
    if command -v minikube &> /dev/null && minikube status &> /dev/null; then
        echo ""
        echo "📍 Loading images to Minikube..."
        minikube image load $API_IMAGE 2>/dev/null && echo "✅ API image loaded" || true
        minikube image load $FRONTEND_IMAGE 2>/dev/null && echo "✅ Frontend image loaded" || true
    fi
fi
echo ""

# Step 4: Deploy with Kustomize
echo "📋 Step 4: Deploying resources with Kustomize..."
if kubectl apply -k k8s/ 2>&1 | tee /tmp/deploy.log; then
    echo "✅ Resources deployed successfully"
else
    echo "❌ Deployment failed. Check /tmp/deploy.log for details"
    exit 1
fi
echo ""

# Step 5: Wait for pods
echo "📋 Step 5: Waiting for pods to be ready..."
echo "This may take a few minutes..."
kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s 2>/dev/null || echo "⚠️  PostgreSQL pod not ready yet"
kubectl wait --for=condition=ready pod -l app=redis -n $NAMESPACE --timeout=60s 2>/dev/null || echo "⚠️  Redis pod not ready yet"
kubectl wait --for=condition=ready pod -l app=minio -n $NAMESPACE --timeout=60s 2>/dev/null || echo "⚠️  MinIO pod not ready yet"
echo "✅ Core services ready"
echo ""

# Step 6: Display pod status
echo "📋 Step 6: Pod Status"
kubectl get pods -n $NAMESPACE -o wide
echo ""

# Step 7: Display services
echo "📋 Step 7: Services"
kubectl get svc -n $NAMESPACE
echo ""

# Step 8: Show access information
echo "🌐 Access Information:"
echo "===================="
echo ""
if [ "$CLUSTER_TYPE" = "local" ]; then
    echo "Use port forwarding to access services:"
    echo ""
    echo "# API (FastAPI)"
    echo "kubectl port-forward -n $NAMESPACE svc/api 8000:8000"
    echo "Then visit: http://localhost:8000/docs"
    echo ""
    echo "# Frontend"
    echo "kubectl port-forward -n $NAMESPACE svc/frontend 3000:80"
    echo "Then visit: http://localhost:3000"
    echo ""
    echo "# MinIO Console"
    echo "kubectl port-forward -n $NAMESPACE svc/minio 9001:9001"
    echo "Then visit: http://localhost:9001"
    echo ""
    echo "# PostgreSQL"
    echo "kubectl port-forward -n $NAMESPACE svc/postgres 5432:5432"
    echo ""
    echo "# Redis"
    echo "kubectl port-forward -n $NAMESPACE svc/redis 6379:6379"
else
    echo "Ingress endpoints:"
    kubectl get ingress -n $NAMESPACE -o wide
fi
echo ""

# Step 9: Useful commands
echo "📚 Useful Commands:"
echo "=================="
echo ""
echo "# View logs"
echo "kubectl logs -f -n $NAMESPACE -l app=api"
echo ""
echo "# Scale a deployment"
echo "kubectl scale deployment api --replicas=3 -n $NAMESPACE"
echo ""
echo "# Exec into a pod"
echo "kubectl exec -it -n $NAMESPACE <pod-name> -- /bin/sh"
echo ""
echo "# Watch pod status"
echo "kubectl get pods -n $NAMESPACE -w"
echo ""
echo "# Delete all resources"
echo "kubectl delete namespace $NAMESPACE"
echo ""

echo "✅ Deployment complete!"
