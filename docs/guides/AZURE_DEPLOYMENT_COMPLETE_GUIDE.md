# 🚀 NEPSE AI Trading Bot - Azure Deployment Guide

**Budget:** $100/year Azure Student Credit  
**Target Duration:** 7-8 months  
**Domains:**

- Frontend: `nepse.sijanpaudel.com.np`
- Backend: `nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io`

---

## 📊 Cost Analysis & Best Architecture

### Recommended Architecture (Most Cost-Effective)

| Service                       | Component              | Monthly Cost  | Why                                       |
| ----------------------------- | ---------------------- | ------------- | ----------------------------------------- |
| **Azure Static Web Apps**     | Frontend (Next.js)     | **FREE**      | Perfect for SSG, includes SSL, global CDN |
| **Azure Container Apps**      | Backend (FastAPI)      | **~$5-10/mo** | Scales to zero, pay-per-use               |
| **Azure Cosmos DB Free Tier** | Database (MongoDB API) | **FREE**      | 1000 RU/s, 25GB free forever              |

**Total Estimated Cost: $5-10/month = $40-80 for 8 months** ✅

### Alternative Options (More Expensive)

| Option                     | Cost/Month | Pros         | Cons                      |
| -------------------------- | ---------- | ------------ | ------------------------- |
| App Service B1 + Container | ~$13       | Simple       | Uses whole budget in ~7mo |
| ACI (Container Instances)  | ~$8-15     | Easy         | No scale-to-zero          |
| VM B1s                     | ~$8        | Full control | Manual management         |

---

## 🛠️ Prerequisites Checklist

```bash
# 1. Install Azure CLI
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# 2. Verify installation
az --version

# 3. Install Docker (for building container images)
sudo apt install docker.io
sudo usermod -aG docker $USER
# Log out and back in for group changes

# 4. Install Node.js (for frontend build)
# Already installed if you ran yarn dev
```

---

## 📝 Step-by-Step Deployment

### Phase 1: Azure Login & Setup

```bash
# Step 1.1: Login to Azure
az login

# Step 1.2: Verify your subscription (should show Student subscription)
az account show --query "{Name:name, ID:id, State:state}"

# Step 1.3: Set default region (Southeast Asia is closest to Nepal)
az configure --defaults location=southeastasia

# Step 1.4: Create Resource Group (container for all resources)
az group create \
  --name rg-nepse-trading \
  --location southeastasia \
  --tags Environment=Production Project=NepseTrading
```

**Expected Output:**

```json
{
  "id": "/subscriptions/.../resourceGroups/rg-nepse-trading",
  "location": "southeastasia",
  "name": "rg-nepse-trading",
  "properties": { "provisioningState": "Succeeded" }
}
```

---

### Phase 2: Setup Azure Container Registry (ACR)

ACR stores your Docker images. Basic tier = ~$5/month, but we'll use **Free tier trick**.

```bash
# Step 2.1: Create Container Registry (Basic tier - cheapest)
az acr create \
  --resource-group rg-nepse-trading \
  --name nepseacr$(date +%s | tail -c 6) \
  --sku Basic \
  --admin-enabled true

# IMPORTANT: Note the registry name! Example: nepseacr123456
# Store it in variable:
export ACR_NAME="nepseacr123456"  # Replace with your actual name

# Step 2.2: Get ACR credentials
az acr credential show --name $ACR_NAME --query "{username:username, password:passwords[0].value}"
```

**Save these credentials!** You'll need them later.

---

### Phase 3: Build & Push Backend Docker Image

```bash
# Step 3.1: Navigate to backend directory
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse_ai_trading

# Step 3.2: Login to ACR
az acr login --name $ACR_NAME

# Step 3.3: Build Docker image
docker build -t nepse-api:v1 .

# Step 3.4: Tag for ACR
docker tag nepse-api:v1 $ACR_NAME.azurecr.io/nepse-api:v1

# Step 3.5: Push to ACR
docker push $ACR_NAME.azurecr.io/nepse-api:v1

# Step 3.6: Verify image is in registry
az acr repository list --name $ACR_NAME --output table
```

---

### Phase 4: Create Azure Cosmos DB (Free Tier - MongoDB API)

```bash
# Step 4.1: Create Cosmos DB account with MongoDB API (FREE TIER)
az cosmosdb create \
  --name nepse-cosmos-db \
  --resource-group rg-nepse-trading \
  --kind MongoDB \
  --server-version 4.2 \
  --default-consistency-level Session \
  --locations regionName=southeastasia failoverPriority=0 isZoneRedundant=False \
  --enable-free-tier true \
  --capabilities EnableMongo

# ⏳ This takes 5-10 minutes! Wait for it to complete.

# Step 4.2: Get connection string
az cosmosdb keys list \
  --name nepse-cosmos-db \
  --resource-group rg-nepse-trading \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv
```

**Save the connection string!** Format:

```
mongodb://nepse-cosmos-db:PRIMARY_KEY@nepse-cosmos-db.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&...
```

---

### Phase 5: Deploy Backend with Azure Container Apps

Container Apps is the **most cost-effective** for low-traffic APIs. It scales to zero!

```bash
# Step 5.1: Install Container Apps extension
az extension add --name containerapp --upgrade

# Step 5.2: Create Container Apps Environment
az containerapp env create \
  --name nepse-env \
  --resource-group rg-nepse-trading \
  --location southeastasia

# Step 5.3: Create the Container App
az containerapp create \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --environment nepse-env \
  --image $ACR_NAME.azurecr.io/nepse-api:v1 \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $(az acr credential show -n $ACR_NAME --query username -o tsv) \
  --registry-password $(az acr credential show -n $ACR_NAME --query "passwords[0].value" -o tsv) \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --env-vars \
    "MONGODB_URL=<YOUR_COSMOS_CONNECTION_STRING>" \
    "OPENAI_API_KEY=<YOUR_OPENAI_KEY>" \
    "TELEGRAM_BOT_TOKEN=<YOUR_TELEGRAM_TOKEN>" \
    "ENVIRONMENT=production"

# Step 5.4: Get the API URL
az containerapp show \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --query "properties.configuration.ingress.fqdn" -o tsv
```

**Expected Output:** `nepse-api.bluesky-abc123.southeastasia.azurecontainerapps.io`

---

### Phase 6: Build & Deploy Frontend (Azure Static Web Apps)

Static Web Apps is **FREE** and perfect for Next.js!

#### 6.1: Update Next.js for Static Export

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse-saas-frontend
```

Edit `next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // Enable static export
  trailingSlash: true,
  images: {
    unoptimized: true, // Required for static export
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ||
      'https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io',
  },
}

export default nextConfig
```

#### 6.2: Build Static Export

```bash
# Build the static site
yarn build

# This creates an 'out' directory with static files
ls -la out/
```

#### 6.3: Create Static Web App via Azure Portal (Easiest Method)

1. Go to [Azure Portal](https://portal.azure.com)
2. Search "Static Web Apps" → Create
3. Fill in:
   - **Subscription:** Azure for Students
   - **Resource Group:** rg-nepse-trading
   - **Name:** nepse-frontend
   - **Plan type:** Free
   - **Region:** East Asia (closest available)
   - **Source:** Other (we'll deploy via CLI)
4. Click "Review + Create" → "Create"

#### 6.4: Deploy via SWA CLI

```bash
# Install SWA CLI
npm install -g @azure/static-web-apps-cli

# Get deployment token from Azure Portal:
# Static Web App → Overview → Manage deployment token → Copy

# Deploy
swa deploy ./out \
  --deployment-token <YOUR_DEPLOYMENT_TOKEN> \
  --env production
```

---

### Phase 7: Configure Custom Domain (nepse.sijanpaudel.com.np)

#### 7.1: For Frontend (Static Web App)

1. **Azure Portal** → Static Web Apps → nepse-frontend → Custom domains
2. Click "Add" → Enter `nepse.sijanpaudel.com.np`
3. Azure will show you DNS records to add

**Add to your DNS (sijanpaudel.com.np):**

```
Type: CNAME
Name: nepse
Value: <your-swa-url>.azurestaticapps.net
TTL: 3600
```

#### 7.2: For Backend API (Container App)

```bash
# Add custom domain to Container App
az containerapp hostname add \
  --hostname nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io \
  --resource-group rg-nepse-trading \
  --name nepse-api

# Get the verification TXT record
az containerapp hostname show \
  --hostname nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io \
  --resource-group rg-nepse-trading \
  --name nepse-api
```

**Add to your DNS:**

```
# CNAME Record
Type: CNAME
Name: api.nepse
Value: nepse-api.<random>.southeastasia.azurecontainerapps.io
TTL: 3600

# TXT Record (for verification)
Type: TXT
Name: asuid.api.nepse
Value: <verification-code-from-azure>
TTL: 3600
```

#### 7.3: Enable SSL (Free with Azure)

```bash
# For Container App - SSL is automatic after domain verification
az containerapp hostname bind \
  --hostname nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io \
  --resource-group rg-nepse-trading \
  --name nepse-api \
  --certificate-type managed

# For Static Web App - SSL is automatic!
```

---

### Phase 8: Environment Variables Reference

#### Backend Container App (.env equivalent)

```bash
# Update environment variables
az containerapp update \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --set-env-vars \
    "MONGODB_URL=mongodb://..." \
    "OPENAI_API_KEY=sk-..." \
    "TELEGRAM_BOT_TOKEN=123456:ABC..." \
    "CORS_ORIGINS=https://nepse.sijanpaudel.com.np" \
    "ENVIRONMENT=production"
```

#### Frontend (.env.production)

```bash
# Create .env.production in nepse-saas-frontend/
NEXT_PUBLIC_API_URL=https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io
```

---

## 🔍 Monitoring & Cost Management

### Check Current Costs

```bash
# View cost analysis
az costmanagement query \
  --scope "/subscriptions/$(az account show --query id -o tsv)" \
  --type Usage \
  --timeframe MonthToDate
```

### Set Budget Alert (Very Important!)

```bash
# Create budget alert at $10/month
az consumption budget create \
  --budget-name "Monthly-Limit" \
  --amount 12 \
  --time-grain Monthly \
  --start-date 2024-01-01 \
  --end-date 2025-12-31 \
  --resource-group rg-nepse-trading \
  --category Cost
```

### View Container App Logs

```bash
# Stream logs
az containerapp logs show \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --follow
```

---

## 📋 Quick Reference Commands

```bash
# Restart API
az containerapp revision restart \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --revision $(az containerapp revision list -n nepse-api -g rg-nepse-trading --query "[0].name" -o tsv)

# Scale API (if needed)
az containerapp update \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --min-replicas 1 \
  --max-replicas 3

# Update API image after code changes
docker build -t nepse-api:v2 .
docker tag nepse-api:v2 $ACR_NAME.azurecr.io/nepse-api:v2
docker push $ACR_NAME.azurecr.io/nepse-api:v2
az containerapp update \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --image $ACR_NAME.azurecr.io/nepse-api:v2

# Delete everything (when done)
az group delete --name rg-nepse-trading --yes --no-wait
```

---

## 💰 Cost Breakdown Summary

| Resource           | SKU                      | Monthly Cost    |
| ------------------ | ------------------------ | --------------- |
| Static Web App     | Free                     | $0              |
| Container Apps     | Consumption (scale to 0) | $3-8            |
| Container Registry | Basic                    | $5              |
| Cosmos DB          | Free Tier                | $0              |
| Custom Domain SSL  | Free                     | $0              |
| **Total**          |                          | **$8-13/month** |

**8 months = $64-104** → Fits within $100 budget! ✅

---

## 🚨 Troubleshooting

### API Not Starting

```bash
# Check logs
az containerapp logs show --name nepse-api --resource-group rg-nepse-trading --tail 100

# Common issues:
# - Missing env vars → Update with az containerapp update --set-env-vars
# - Wrong port → Ensure Dockerfile EXPOSE 8000 and --target-port 8000
```

### Domain Not Working

```bash
# Verify DNS propagation
nslookup nepse.sijanpaudel.com.np
nslookup nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io

# DNS can take up to 48 hours to propagate globally
```

### CORS Errors

```bash
# Update CORS in backend
az containerapp update \
  --name nepse-api \
  --resource-group rg-nepse-trading \
  --set-env-vars "CORS_ORIGINS=https://nepse.sijanpaudel.com.np,http://localhost:3000"
```

---

## ✅ Final Checklist

- [ ] Azure CLI installed and logged in
- [ ] Resource group created
- [ ] Container Registry created and image pushed
- [ ] Cosmos DB created (free tier)
- [ ] Container App deployed with env vars
- [ ] Static Web App deployed
- [ ] DNS configured for both domains
- [ ] SSL certificates active
- [ ] Budget alert set
- [ ] Test both endpoints working

---

**Created:** March 2024  
**Estimated Deployment Time:** 1-2 hours  
**Support:** Open an issue on GitHub
