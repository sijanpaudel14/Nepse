#!/bin/bash
# =============================================================================
# Deploy Backend to Azure (Manual)
# Use this to manually deploy backend after code changes
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   NEPSE Backend - Manual Deployment${NC}"
echo -e "${BLUE}================================================${NC}"

RG="rg-nepse-trading"
ACR_NAME=$(cat /tmp/nepse-acr-name 2>/dev/null || az acr list -g $RG --query "[0].name" -o tsv)
IMAGE_TAG="v$(date +%Y%m%d-%H%M%S)"

echo ""
echo "Configuration:"
echo "  Resource Group: $RG"
echo "  ACR: $ACR_NAME"
echo "  Image Tag: $IMAGE_TAG"
echo ""

# Step 1: Build Docker image
echo -e "${GREEN}[1/5]${NC} Building Docker image..."
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse_ai_trading
docker build -t nepse-api:$IMAGE_TAG .
echo "✓ Image built"

# Step 2: Login to ACR
echo -e "\n${GREEN}[2/5]${NC} Logging into Azure Container Registry..."
az acr login --name $ACR_NAME
echo "✓ Logged in"

# Step 3: Tag and push
echo -e "\n${GREEN}[3/5]${NC} Pushing to ACR..."
docker tag nepse-api:$IMAGE_TAG $ACR_NAME.azurecr.io/nepse-api:$IMAGE_TAG
docker tag nepse-api:$IMAGE_TAG $ACR_NAME.azurecr.io/nepse-api:latest
docker push $ACR_NAME.azurecr.io/nepse-api:$IMAGE_TAG
docker push $ACR_NAME.azurecr.io/nepse-api:latest
echo "✓ Image pushed"

# Step 4: Update Container App
echo -e "\n${GREEN}[4/5]${NC} Updating Azure Container App..."
az containerapp update \
  --name nepse-api \
  --resource-group $RG \
  --image $ACR_NAME.azurecr.io/nepse-api:$IMAGE_TAG \
  --output none
echo "✓ Container App updated"

# Step 5: Verify deployment
echo -e "\n${GREEN}[5/5]${NC} Verifying deployment..."
sleep 15

BACKEND_URL=$(az containerapp show \
  --name nepse-api \
  --resource-group $RG \
  --query "properties.configuration.ingress.fqdn" -o tsv)

echo "Testing health endpoint..."
if curl -f https://$BACKEND_URL/health 2>/dev/null; then
    echo "✓ Backend is healthy"
else
    echo -e "${YELLOW}⚠ Health check failed. Check logs:${NC}"
    echo "  az containerapp logs show -n nepse-api -g $RG --follow"
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Backend URL: https://$BACKEND_URL"
echo ""
echo "Test endpoints:"
echo "  Health: https://$BACKEND_URL/health"
echo "  API Docs: https://$BACKEND_URL/docs"
echo ""
echo -e "${YELLOW}Check logs:${NC}"
echo "  az containerapp logs show -n nepse-api -g $RG --follow"
