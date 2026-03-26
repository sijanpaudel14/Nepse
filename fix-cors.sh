#!/bin/bash
# =============================================================================
# Fix Backend CORS to Allow Frontend Connection
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   Fixing Backend CORS${NC}"
echo -e "${BLUE}================================================${NC}"

RG="rg-nepse-trading"

# Get URLs
echo -e "\n${GREEN}[1/3]${NC} Getting deployment URLs..."
BACKEND_URL=$(az containerapp show -n nepse-api -g $RG --query "properties.configuration.ingress.fqdn" -o tsv)
STORAGE_NAME=$(cat /tmp/nepse-storage-name 2>/dev/null || az storage account list -g $RG --query "[0].name" -o tsv)
FRONTEND_URL="https://$STORAGE_NAME.z12.web.core.windows.net"

echo "Backend: https://$BACKEND_URL"
echo "Frontend: $FRONTEND_URL"

# Update CORS environment variable
echo -e "\n${GREEN}[2/3]${NC} Updating backend CORS settings..."
az containerapp update \
  --name nepse-api \
  --resource-group $RG \
  --set-env-vars \
    "FRONTEND_URL=$FRONTEND_URL" \
  --output none

# Restart backend
echo -e "\n${GREEN}[3/3]${NC} Restarting backend..."
az containerapp revision restart \
  --name nepse-api \
  --resource-group $RG \
  --output none

echo ""
echo -e "${GREEN}✓ Backend updated and restarted${NC}"
echo ""
echo "Wait 30 seconds, then test your frontend:"
echo "  $FRONTEND_URL"
echo ""
echo "Test backend health:"
echo "  curl https://$BACKEND_URL/health"
