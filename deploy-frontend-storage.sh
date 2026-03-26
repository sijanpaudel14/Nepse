#!/bin/bash
# =============================================================================
# Deploy NEPSE Frontend to Azure Storage Static Website
# =============================================================================
# This uses Azure Storage ($0.50/month) as it's the cheapest option
# =============================================================================

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   NEPSE Frontend - Storage Deployment${NC}"
echo -e "${BLUE}================================================${NC}"

# Configuration
RG="rg-nepse"
STORAGE_NAME="nepsestorage$(date +%s | tail -c 8)"
LOCATION="koreacentral"  # Allowed by policy

# Step 1: Create Storage Account
echo -e "\n${GREEN}[1/6]${NC} Creating Storage Account..."
az storage account create \
  --name $STORAGE_NAME \
  --resource-group $RG \
  --location $LOCATION \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access true \
  --output none
echo "✓ Storage account created: $STORAGE_NAME"

# Step 2: Enable Static Website
echo -e "\n${GREEN}[2/6]${NC} Enabling static website hosting..."
az storage blob service-properties update \
  --account-name $STORAGE_NAME \
  --static-website \
  --index-document index.html \
  --404-document 404.html \
  --auth-mode login
echo "✓ Static website enabled"

# Step 3: Get Backend API URL
echo -e "\n${GREEN}[3/6]${NC} Getting backend API URL..."
BACKEND_URL=$(az containerapp show \
  --name nepse-api \
  --resource-group $RG \
  --query "properties.configuration.ingress.fqdn" -o tsv)

if [ -z "$BACKEND_URL" ]; then
    echo -e "${YELLOW}Warning: Backend API not found. Using placeholder.${NC}"
    BACKEND_URL="api.example.com"
fi

echo "✓ Backend URL: https://$BACKEND_URL"

# Step 4: Build Frontend
echo -e "\n${GREEN}[4/6]${NC} Building frontend..."
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse-saas-frontend

# Create production env
echo "NEXT_PUBLIC_API_URL=https://$BACKEND_URL" > .env.production

# Build static export
BUILD_MODE=static yarn build
echo "✓ Build completed"

# Step 5: Deploy to Storage
echo -e "\n${GREEN}[5/6]${NC} Uploading to Azure Storage..."

# Get storage key
STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE_NAME \
  --resource-group $RG \
  --query "[0].value" -o tsv)

# Upload all files
az storage blob upload-batch \
  --account-name $STORAGE_NAME \
  --account-key $STORAGE_KEY \
  --destination '$web' \
  --source ./out \
  --overwrite \
  --no-progress

echo "✓ Files uploaded"

# Step 6: Get Public URL
echo -e "\n${GREEN}[6/6]${NC} Deployment complete!"

PUBLIC_URL=$(az storage account show \
  --name $STORAGE_NAME \
  --resource-group $RG \
  --query "primaryEndpoints.web" -o tsv)

echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}   Frontend Deployed Successfully!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "Public URL: $PUBLIC_URL"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Test the website:"
echo "   Open: $PUBLIC_URL"
echo ""
echo "2. To setup custom domain (nepse.sijanpaudel.com.np):"
echo "   Add DNS CNAME record:"
echo "   Name: nepse"
echo "   Value: $STORAGE_NAME.z12.web.core.windows.net"
echo ""
echo "3. Then run:"
echo "   az storage account update \\"
echo "     --name $STORAGE_NAME \\"
echo "     --resource-group $RG \\"
echo "     --custom-domain nepse.sijanpaudel.com.np"
echo ""
echo -e "${YELLOW}Note:${NC} For SSL/HTTPS on custom domain, you'll need Azure CDN."
echo "See: docs/guides/AZURE_STORAGE_CDN_SSL.md for SSL setup"
echo ""

# Save storage name for future updates
echo $STORAGE_NAME > /tmp/nepse-storage-name
echo "Storage name saved to: /tmp/nepse-storage-name"
