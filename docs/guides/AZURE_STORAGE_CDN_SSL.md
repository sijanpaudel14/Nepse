# 🔒 Enable SSL on Custom Domain (Azure Storage + CDN)

## Problem
Azure Storage Static Website doesn't support SSL on custom domains by default.

## Solution
Use Azure CDN (Standard Microsoft) - Adds ~$2/month but provides:
- ✅ Free SSL certificate
- ✅ Global CDN (faster loading)
- ✅ Custom domain support

---

## Step-by-Step SSL Setup

### Step 1: Create CDN Profile

```bash
# Variables
RG="rg-nepse"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)  # From previous deployment

# Create CDN profile (Standard Microsoft - cheapest with SSL)
az cdn profile create \
  --name nepse-cdn \
  --resource-group $RG \
  --sku Standard_Microsoft \
  --location koreacentral
```

### Step 2: Create CDN Endpoint

```bash
# Create endpoint pointing to your storage
az cdn endpoint create \
  --name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --origin $STORAGE_NAME.z12.web.core.windows.net \
  --origin-host-header $STORAGE_NAME.z12.web.core.windows.net \
  --enable-compression true \
  --content-types-to-compress \
    "text/html" \
    "text/css" \
    "application/javascript" \
    "application/json"

# Get CDN URL
az cdn endpoint show \
  --name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --query "hostName" -o tsv
```

Your site is now available at: `nepse.azureedge.net`

### Step 3: Add Custom Domain

**First, configure DNS at your domain registrar:**

```
Type: CNAME
Name: nepse
Value: nepse.azureedge.net
TTL: 3600
```

**Wait 5-10 minutes for DNS propagation**, then:

```bash
# Verify DNS is working
nslookup nepse.sijanpaudel.com.np

# Add custom domain to CDN
az cdn custom-domain create \
  --endpoint-name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --name nepse-custom \
  --hostname nepse.sijanpaudel.com.np
```

### Step 4: Enable HTTPS (Free SSL)

```bash
# Enable managed SSL certificate (takes 6-8 hours to provision)
az cdn custom-domain enable-https \
  --endpoint-name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --name nepse-custom \
  --min-tls-version 1.2

echo "✓ SSL certificate requested"
echo "⏳ Certificate provisioning takes 6-8 hours"
echo "Check status with: az cdn custom-domain show ..."
```

### Step 5: Check SSL Status

```bash
# Check certificate status
az cdn custom-domain show \
  --endpoint-name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --name nepse-custom \
  --query "{Domain:hostName, SSL:customHttpsProvisioningState}" -o table

# When customHttpsProvisioningState shows "Enabled", SSL is active
```

---

## Complete Automation Script

```bash
#!/bin/bash
# deploy-frontend-with-ssl.sh

set -e

RG="rg-nepse"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
CUSTOM_DOMAIN="nepse.sijanpaudel.com.np"

echo "Creating CDN for SSL support..."

# Create CDN
az cdn profile create \
  --name nepse-cdn \
  --resource-group $RG \
  --sku Standard_Microsoft \
  --location koreacentral \
  --output none

# Create endpoint
az cdn endpoint create \
  --name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --origin $STORAGE_NAME.z12.web.core.windows.net \
  --origin-host-header $STORAGE_NAME.z12.web.core.windows.net \
  --enable-compression true \
  --output none

CDN_URL=$(az cdn endpoint show -n nepse --profile-name nepse-cdn -g $RG -q "hostName" -o tsv)

echo "✓ CDN created: https://$CDN_URL"
echo ""
echo "Add this DNS record:"
echo "  CNAME  nepse  →  $CDN_URL"
echo ""
read -p "Press ENTER after adding DNS record..."

# Add custom domain
az cdn custom-domain create \
  --endpoint-name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --name nepse-custom \
  --hostname $CUSTOM_DOMAIN \
  --output none

# Enable SSL
az cdn custom-domain enable-https \
  --endpoint-name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --name nepse-custom \
  --min-tls-version 1.2 \
  --output none

echo "✓ SSL certificate requested"
echo "⏳ Certificate provisioning: 6-8 hours"
echo ""
echo "Your site will be available at:"
echo "  https://$CUSTOM_DOMAIN"
```

---

## Update Deployment Script (For Future Updates)

```bash
#!/bin/bash
# update-frontend.sh - Update website after code changes

set -e

RG="rg-nepse"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)

# Rebuild
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse-saas-frontend
BUILD_MODE=static yarn build

# Upload
STORAGE_KEY=$(az storage account keys list -n $STORAGE_NAME -g $RG -q "[0].value" -o tsv)
az storage blob upload-batch \
  --account-name $STORAGE_NAME \
  --account-key $STORAGE_KEY \
  --destination '$web' \
  --source ./out \
  --overwrite

# Purge CDN cache (if using CDN)
az cdn endpoint purge \
  --name nepse \
  --profile-name nepse-cdn \
  --resource-group $RG \
  --content-paths "/*" \
  --no-wait

echo "✓ Frontend updated!"
```

---

## Cost Summary with CDN

| Service | Monthly Cost |
|---------|-------------|
| Storage Static Website | $0.50 |
| CDN Standard Microsoft | $2-3 |
| SSL Certificate | FREE |
| **Total Frontend** | **$2.50-3.50** |
| Backend (Container Apps) | $8-10 |
| Container Registry | $5 |
| **Grand Total** | **$15.50-18.50/month** |

**6 months = $93-111** → Still close to budget!

---

## Alternative: Skip CDN (No SSL on Custom Domain)

If you want to save $2-3/month and don't need SSL:

1. Skip CDN setup
2. Point DNS directly to storage:
   ```
   CNAME  nepse  →  <storage>.z12.web.core.windows.net
   ```
3. Accept that custom domain will be HTTP only
4. Backend API will still have SSL (Container Apps includes it free)

**Note:** Modern browsers show "Not Secure" warning for HTTP sites.
