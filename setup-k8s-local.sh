#!/bin/bash
# Quick setup script for local Kubernetes development

set -e

echo "🚀 Quick K8s Setup for Local Development"
echo "========================================"

# Check prerequisites
echo ""
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    exit 1
fi
echo "✅ Docker found"

if ! command -v minikube &> /dev/null && ! kubectl config current-context &>/dev/null; then
    echo "❌ Kubernetes not configured (install Minikube or connect to cluster)"
    exit 1
fi
echo "✅ Kubernetes configured"

# Build Docker images
echo ""
echo "📍 Building Docker images..."

echo "Building API image..."
docker build -f admin-api/Dockerfile -t marketing-video-agent:latest .
echo "✅ API image built"

echo "Building frontend image..."
docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest .
echo "✅ Frontend image built"

# Load to Minikube if running
echo ""
if command -v minikube &> /dev/null && minikube status &> /dev/null; then
    echo "📍 Loading images to Minikube..."
    minikube image load marketing-video-agent:latest
    minikube image load marketing-video-agent-frontend:latest
    echo "✅ Images loaded to Minikube"
fi

# Deploy
echo ""
echo "📍 Deploying to Kubernetes..."
bash deploy-k8s.sh local

echo ""
echo "✅ Setup complete!"
