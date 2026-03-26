#!/bin/bash
# =============================================================================
# Create Azure Container Registry (ACR)
# Required for storing Docker images for backend deployment
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   Creating Azure Container Registry${NC}"
echo -e "${BLUE}================================================${NC}"

RG="rg-nepse-trading"
LOCATION="koreacentral"  # Or your allowed region
ACR_NAME="nepseacr$(date +%s | tail -c 6)"

echo ""
echo "Configuration:"
echo "  Resource Group: $RG"
echo "  Location: $LOCATION"
echo "  ACR Name: $ACR_NAME"
echo ""

# Check if resource group exists
if ! az group show -n $RG &>/dev/null; then
    echo -e "${YELLOW}Resource group $RG doesn't exist. Creating...${NC}"
    az group create -n $RG -l $LOCATION --output none
    echo "✓ Resource group created"
fi

# Create ACR
echo -e "\n${GREEN}[1/3]${NC} Creating Azure Container Registry..."
az acr create \
  --name $ACR_NAME \
  --resource-group $RG \
  --location $LOCATION \
  --sku Basic \
  --admin-enabled true \
  --output none

echo "✓ ACR created: $ACR_NAME"

# Get credentials
echo -e "\n${GREEN}[2/3]${NC} Getting ACR credentials..."
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)

echo "✓ Credentials retrieved"

# Save ACR name for other scripts
echo -e "\n${GREEN}[3/3]${NC} Saving ACR name..."
echo $ACR_NAME > /tmp/nepse-acr-name
echo "✓ ACR name saved to: /tmp/nepse-acr-name"

# Display info
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}   ACR Created Successfully!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""
echo "ACR Name: $ACR_NAME"
echo "Login Server: $ACR_LOGIN_SERVER"
echo "Username: $ACR_USERNAME"
echo ""
echo -e "${YELLOW}For GitHub Actions:${NC}"
echo "ACR_NAME secret value: $ACR_NAME"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. This ACR will be used to store your backend Docker images"
echo "2. Run ./setup-github-secrets.sh to generate all GitHub secrets"
echo "3. Or continue with backend deployment"
echo ""
echo "Cost: ~$5/month (Basic tier)"
