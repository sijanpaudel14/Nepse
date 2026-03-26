#!/bin/bash
# =============================================================================
# NEPSE AI Trading Bot - Azure Deployment Script
# =============================================================================
# This script automates the Azure deployment process
# Run: chmod +x deploy-azure.sh && ./deploy-azure.sh
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RESOURCE_GROUP="rg-nepse-trading"
LOCATION="southeastasia"
ACR_NAME="nepseacr$(date +%s | tail -c 6)"
COSMOS_NAME="nepse-cosmos-db"
CONTAINER_ENV="nepse-env"
CONTAINER_APP="nepse-api"
STATIC_WEB_APP="nepse-frontend"

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   NEPSE AI Trading Bot - Azure Deployment${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to print step
step() {
    echo -e "\n${GREEN}[STEP]${NC} $1"
}

# Function to print warning
warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to print error
error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check prerequisites
step "Checking prerequisites..."

if ! command -v az &> /dev/null; then
    error "Azure CLI not installed. Run: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
fi

if ! command -v docker &> /dev/null; then
    error "Docker not installed. Run: sudo apt install docker.io"
fi

# Check Azure login
step "Checking Azure login status..."
if ! az account show &> /dev/null; then
    echo "Not logged in. Opening browser for login..."
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
echo -e "Logged in to subscription: ${GREEN}$SUBSCRIPTION${NC}"

# Confirm deployment
echo ""
echo -e "${YELLOW}Deployment Configuration:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  ACR Name: $ACR_NAME"
echo ""
read -p "Continue with deployment? (y/n): " confirm
if [[ $confirm != "y" && $confirm != "Y" ]]; then
    echo "Deployment cancelled."
    exit 0
fi

# Phase 1: Create Resource Group
step "Creating Resource Group..."
az group create \
    --name $RESOURCE_GROUP \
    --location $LOCATION \
    --tags Environment=Production Project=NepseTrading \
    --output none
echo "✓ Resource Group created"

# Phase 2: Create Container Registry
step "Creating Azure Container Registry..."
az acr create \
    --resource-group $RESOURCE_GROUP \
    --name $ACR_NAME \
    --sku Basic \
    --admin-enabled true \
    --output none
echo "✓ Container Registry created: $ACR_NAME"

# Save ACR name for later
echo $ACR_NAME > .azure-acr-name

# Phase 3: Build and Push Docker Image
step "Building Docker image..."
cd ../nepse_ai_trading
docker build -t nepse-api:v1 .
echo "✓ Docker image built"

step "Pushing to Azure Container Registry..."
az acr login --name $ACR_NAME
docker tag nepse-api:v1 $ACR_NAME.azurecr.io/nepse-api:v1
docker push $ACR_NAME.azurecr.io/nepse-api:v1
echo "✓ Image pushed to ACR"

# Phase 4: Create Cosmos DB (Free Tier)
step "Creating Cosmos DB with MongoDB API (FREE TIER)..."
echo "  ⏳ This takes 5-10 minutes..."
az cosmosdb create \
    --name $COSMOS_NAME \
    --resource-group $RESOURCE_GROUP \
    --kind MongoDB \
    --server-version 4.2 \
    --default-consistency-level Session \
    --locations regionName=$LOCATION failoverPriority=0 isZoneRedundant=False \
    --enable-free-tier true \
    --capabilities EnableMongo \
    --output none
echo "✓ Cosmos DB created"

# Get connection string
MONGO_URL=$(az cosmosdb keys list \
    --name $COSMOS_NAME \
    --resource-group $RESOURCE_GROUP \
    --type connection-strings \
    --query "connectionStrings[0].connectionString" -o tsv)
echo "✓ MongoDB connection string retrieved"

# Phase 5: Create Container Apps Environment
step "Creating Container Apps Environment..."
az extension add --name containerapp --upgrade --yes 2>/dev/null || true
az containerapp env create \
    --name $CONTAINER_ENV \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --output none
echo "✓ Container Apps Environment created"

# Get user input for secrets
echo ""
echo -e "${YELLOW}Enter your API keys (these will be stored securely in Azure):${NC}"
read -p "OpenAI API Key: " OPENAI_KEY
read -p "Telegram Bot Token: " TELEGRAM_TOKEN

# Phase 6: Deploy Container App
step "Deploying Backend API..."
ACR_USERNAME=$(az acr credential show -n $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show -n $ACR_NAME --query "passwords[0].value" -o tsv)

az containerapp create \
    --name $CONTAINER_APP \
    --resource-group $RESOURCE_GROUP \
    --environment $CONTAINER_ENV \
    --image $ACR_NAME.azurecr.io/nepse-api:v1 \
    --registry-server $ACR_NAME.azurecr.io \
    --registry-username $ACR_USERNAME \
    --registry-password $ACR_PASSWORD \
    --target-port 8000 \
    --ingress external \
    --min-replicas 0 \
    --max-replicas 2 \
    --cpu 0.25 \
    --memory 0.5Gi \
    --env-vars \
        "MONGODB_URL=$MONGO_URL" \
        "OPENAI_API_KEY=$OPENAI_KEY" \
        "TELEGRAM_BOT_TOKEN=$TELEGRAM_TOKEN" \
        "ENVIRONMENT=production" \
    --output none

API_URL=$(az containerapp show \
    --name $CONTAINER_APP \
    --resource-group $RESOURCE_GROUP \
    --query "properties.configuration.ingress.fqdn" -o tsv)
echo "✓ Backend deployed at: https://$API_URL"

# Phase 7: Build Frontend for Static Export
step "Building Frontend for Static Web Apps..."
cd ../nepse-saas-frontend

# Create production env file
echo "NEXT_PUBLIC_API_URL=https://$API_URL" > .env.production

# Build static export
BUILD_MODE=static yarn build

echo "✓ Frontend built"
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}   Deployment Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "Backend API: https://$API_URL"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Deploy frontend to Azure Static Web Apps:"
echo "   - Go to Azure Portal → Create Static Web App"
echo "   - Or run: swa deploy ./out --deployment-token <TOKEN>"
echo ""
echo "2. Configure custom domains in Azure Portal:"
echo "   - nepse.sijanpaudel.com.np → Static Web App"
echo "   - api.nepse.sijanpaudel.com.np → Container App"
echo ""
echo "3. Add DNS records at your domain registrar"
echo ""
echo -e "See: ${BLUE}docs/guides/AZURE_DEPLOYMENT_COMPLETE_GUIDE.md${NC} for detailed instructions"
