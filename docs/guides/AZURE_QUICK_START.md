# ⚡ NEPSE Azure Quick Start (5-Minute Version)

**Budget:** $100/year → ~$10/month → **8 months of runtime** ✅

---

## Step 1: Install Azure CLI (1 min)

```bash
# Install
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login (opens browser)
az login
```

---

## Step 2: Run These Commands (Copy-Paste)

```bash
# Navigate to project
cd /run/media/sijanpaudel/New\ Volume/Nepse

# Set variables
export RG="rg-nepse-trading"
export LOC="southeastasia"
export ACR="nepseacr$(whoami | md5sum | head -c 6)"

# Create everything
az group create -n $RG -l $LOC

az acr create -g $RG -n $ACR --sku Basic --admin-enabled true

az extension add -n containerapp --upgrade -y

az containerapp env create -n nepse-env -g $RG -l $LOC
```

---

## Step 3: Build & Push Docker Image (3 min)

```bash
cd nepse_ai_trading

# Build
docker build -t nepse-api:v1 .

# Login to registry
az acr login -n $ACR

# Push
docker tag nepse-api:v1 $ACR.azurecr.io/nepse-api:v1
docker push $ACR.azurecr.io/nepse-api:v1
```

---

## Step 4: Deploy Backend

```bash
# Deploy (replace YOUR_KEYS)
az containerapp create \
  -n nepse-api \
  -g $RG \
  --environment nepse-env \
  --image $ACR.azurecr.io/nepse-api:v1 \
  --registry-server $ACR.azurecr.io \
  --registry-username $(az acr credential show -n $ACR -q username -o tsv) \
  --registry-password $(az acr credential show -n $ACR -q "passwords[0].value" -o tsv) \
  --target-port 8000 \
  --ingress external \
  --min-replicas 0 \
  --max-replicas 2 \
  --cpu 0.25 \
  --memory 0.5Gi

# Get API URL
az containerapp show -n nepse-api -g $RG -q "properties.configuration.ingress.fqdn" -o tsv
```

---

## Step 5: Deploy Frontend (Free!)

```bash
cd ../nepse-saas-frontend

# Set API URL
echo "NEXT_PUBLIC_API_URL=https://$(az containerapp show -n nepse-api -g $RG -q 'properties.configuration.ingress.fqdn' -o tsv)" > .env.production

# Build static
BUILD_MODE=static yarn build

# Deploy via Azure Portal:
# 1. Portal → Static Web Apps → Create
# 2. Source: Other
# 3. Get deployment token
# 4. Run: npx @azure/static-web-apps-cli deploy ./out --deployment-token <TOKEN>
```

---

## Step 6: Custom Domain Setup

### For nepse.sijanpaudel.com.np (Frontend)

In Azure Portal → Static Web App → Custom domains → Add:

**DNS Record to Add:**
```
CNAME  nepse  → <your-app>.azurestaticapps.net
```

### For api.nepse.sijanpaudel.com.np (Backend)

```bash
az containerapp hostname add \
  --hostname api.nepse.sijanpaudel.com.np \
  -g $RG -n nepse-api
```

**DNS Records to Add:**
```
CNAME  api.nepse  → nepse-api.<random>.azurecontainerapps.io
TXT    asuid.api.nepse  → <verification-code-from-azure>
```

---

## 💡 Monthly Cost Estimate

| Service | Cost |
|---------|------|
| Static Web App | FREE |
| Container Apps (scale-to-zero) | ~$5-8 |
| Container Registry (Basic) | $5 |
| **Total** | **$10-13/mo** |

**8 months = $80-104** → ✅ Fits in $100 budget!

---

## 🔧 Useful Commands

```bash
# View logs
az containerapp logs show -n nepse-api -g $RG --follow

# Restart API
az containerapp revision restart -n nepse-api -g $RG

# Update after code changes
docker build -t nepse-api:v2 .
docker tag nepse-api:v2 $ACR.azurecr.io/nepse-api:v2
docker push $ACR.azurecr.io/nepse-api:v2
az containerapp update -n nepse-api -g $RG --image $ACR.azurecr.io/nepse-api:v2

# DELETE everything when done
az group delete -n $RG --yes
```
