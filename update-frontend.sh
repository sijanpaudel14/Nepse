#!/bin/bash
# =============================================================================
# Update NEPSE Frontend - Redeploy after code changes
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   NEPSE Frontend - Update Deployment${NC}"
echo -e "${BLUE}================================================${NC}"

# Configuration
RG="rg-nepse-trading"

# Check if storage name exists
if [ ! -f /tmp/nepse-storage-name ]; then
    echo "Error: Storage name not found."
    echo "Run ./deploy-frontend-storage.sh first"
    exit 1
fi

STORAGE_NAME=$(cat /tmp/nepse-storage-name)

echo -e "\n${GREEN}[1/4]${NC} Getting backend API URL..."
BACKEND_URL=$(az containerapp show \
  --name nepse-api \
  --resource-group $RG \
  --query "properties.configuration.ingress.fqdn" -o tsv)
echo "✓ Backend: https://$BACKEND_URL"

echo -e "\n${GREEN}[2/4]${NC} Building frontend..."
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse-saas-frontend

echo "NEXT_PUBLIC_API_URL=https://$BACKEND_URL" > .env.production
BUILD_MODE=static yarn build
echo "✓ Build completed"

echo -e "\n${GREEN}[3/4]${NC} Uploading to Azure Storage..."
STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE_NAME \
  --resource-group $RG \
  --query "[0].value" -o tsv)

az storage blob upload-batch \
  --account-name $STORAGE_NAME \
  --account-key $STORAGE_KEY \
  --destination '$web' \
  --source ./out \
  --overwrite \
  --no-progress

echo "✓ Files uploaded"

echo -e "\n${GREEN}[4/4]${NC} Purging CDN cache (if exists)..."
if az cdn endpoint show --name nepse --profile-name nepse-cdn --resource-group $RG &>/dev/null; then
    az cdn endpoint purge \
      --name nepse \
      --profile-name nepse-cdn \
      --resource-group $RG \
      --content-paths "/*" \
      --no-wait
    echo "✓ CDN cache purge initiated"
else
    echo "⊘ No CDN found (skipped)"
fi

echo ""
echo -e "${GREEN}Frontend updated successfully!${NC}"

PUBLIC_URL=$(az storage account show \
  --name $STORAGE_NAME \
  --resource-group $RG \
  --query "primaryEndpoints.web" -o tsv)
echo "View at: $PUBLIC_URL"
