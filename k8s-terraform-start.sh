#!/bin/bash
# All-in-one Terraform + K8s Startup Script
# Usage: bash k8s-terraform-start.sh

set -e

echo "🚀 Marketing Video Agent - Terraform + K8s All-in-One Startup"
echo "=============================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

TERRAFORM_DIR="./terraform"

# Step 1: Verify prerequisites
echo "📋 Step 1: Verifying prerequisites..."
echo ""

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not installed${NC}"
    echo -e "${YELLOW}ℹ️  Install from: https://www.terraform.io/downloads${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Terraform found ($(terraform version -json | grep terraform_version | cut -d'"' -f4))${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker found${NC}"

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ kubectl found${NC}"

# Step 2: Verify Kubernetes
echo ""
echo "📋 Step 2: Verifying Kubernetes..."
if kubectl cluster-info &> /dev/null; then
    echo -e "${GREEN}✅ Kubernetes is running${NC}"
    kubectl cluster-info | grep -E "Kubernetes master|control plane" | head -1
else
    echo -e "${RED}❌ Kubernetes not running${NC}"
    echo -e "${YELLOW}⚠️  Please enable Kubernetes in Docker Desktop:${NC}"
    echo "   1. Open Docker Desktop"
    echo "   2. Settings → Kubernetes"
    echo "   3. Check 'Enable Kubernetes'"
    echo "   4. Wait for it to start"
    echo "   5. Run this script again"
    exit 1
fi

# Step 3: Build images
echo ""
echo "📋 Step 3: Building Docker images..."
echo ""

echo "🔨 Building API image..."
if docker build -f admin-api/Dockerfile -t marketing-video-agent:latest . > /tmp/api-build.log 2>&1; then
    echo -e "${GREEN}✅ API image built${NC}"
else
    echo -e "${RED}❌ Failed to build API image${NC}"
    tail -20 /tmp/api-build.log
    exit 1
fi

echo "🔨 Building Frontend image..."
if docker build -f frontend-admin/Dockerfile -t marketing-video-agent-frontend:latest frontend-admin/ > /tmp/frontend-build.log 2>&1; then
    echo -e "${GREEN}✅ Frontend image built${NC}"
else
    echo -e "${RED}❌ Failed to build Frontend image${NC}"
    tail -20 /tmp/frontend-build.log
    exit 1
fi

# Step 4: Initialize Terraform
echo ""
echo "📋 Step 4: Initializing Terraform..."
if cd "$TERRAFORM_DIR" && terraform init > /tmp/terraform-init.log 2>&1; then
    echo -e "${GREEN}✅ Terraform initialized${NC}"
    cd ..
else
    echo -e "${RED}❌ Terraform initialization failed${NC}"
    tail -20 /tmp/terraform-init.log
    exit 1
fi

# Step 5: Show plan
echo ""
echo "📋 Step 5: Terraform plan"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cd "$TERRAFORM_DIR" && terraform plan -out=tfplan
cd ..

# Step 6: Ask for confirmation
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}⚠️  Review the plan above${NC}"
read -p "Do you want to continue with deployment? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}❌ Deployment cancelled${NC}"
    exit 1
fi

# Step 7: Deploy with Terraform
echo ""
echo "📍 Step 7: Deploying with Terraform..."
if cd "$TERRAFORM_DIR" && terraform apply tfplan; then
    echo -e "${GREEN}✅ Terraform deployment successful${NC}"
    cd ..
else
    echo -e "${RED}❌ Terraform deployment failed${NC}"
    cd ..
    exit 1
fi

# Step 8: Wait for pods
echo ""
echo "📋 Step 8: Waiting for pods to be ready..."
echo "   (This may take 1-2 minutes...)"

max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
    ready=$(kubectl get pods -n video-creator --no-headers 2>/dev/null | wc -l)
    if [ "$ready" -gt 0 ]; then
        all_ready=$(kubectl get pods -n video-creator --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
        echo -ne "\r   Pods running: $all_ready"
        if [ "$all_ready" -ge 3 ]; then
            echo ""
            echo -e "${GREEN}✅ Pods are ready${NC}"
            break
        fi
    fi
    sleep 2
    attempt=$((attempt + 1))
done

# Step 9: Display status
echo ""
echo -e "${BLUE}📊 Kubernetes Status:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl get all -n video-creator

# Step 10: Get outputs
echo ""
echo -e "${BLUE}📤 Terraform Outputs:${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$TERRAFORM_DIR" && terraform output
cd ..

# Step 11: Display next steps
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "🔗 Next steps - Access your application:"
echo ""
echo "   Terminal 1 - API access:"
echo "   $ kubectl port-forward -n video-creator svc/api 9100:9100"
echo "   $ open http://localhost:9100/docs"
echo ""
echo "   Terminal 2 - Frontend access:"
echo "   $ kubectl port-forward -n video-creator svc/frontend 3000:80"
echo "   $ open http://localhost:3000"
echo ""
echo "   Terminal 3 - MinIO access:"
echo "   $ kubectl port-forward -n video-creator svc/minio 9000:9000"
echo "   $ open http://localhost:9000"
echo ""
echo "📝 Terraform commands:"
echo "   • Show plan:        cd terraform && terraform plan"
echo "   • Apply changes:    cd terraform && terraform apply"
echo "   • Show state:       cd terraform && terraform show"
echo "   • Scale API:        cd terraform && terraform apply -var='api_replicas=3'"
echo "   • Destroy all:      cd terraform && terraform destroy"
echo ""
echo "🔍 Kubernetes commands:"
echo "   • View logs:        kubectl logs -f -n video-creator -l app=api"
echo "   • Get status:       kubectl get all -n video-creator"
echo "   • Describe pod:     kubectl describe pod -n video-creator <pod-name>"
echo ""
