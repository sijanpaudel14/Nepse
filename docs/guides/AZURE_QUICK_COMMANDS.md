# ⚡ NEPSE Azure Deployment - Quick Commands

## 🚀 Initial Deployment

### Backend (Already Done ✅)
```bash
# Your backend should already be running
az containerapp show -n nepse-api -g rg-nepse -q "properties.configuration.ingress.fqdn" -o tsv
```

### Frontend (Storage Static Website)
```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./deploy-frontend-storage.sh
```

**That's it!** Your site will be live in ~5 minutes.

---

## 🌐 Custom Domain Setup

### 1. Add DNS Record
```
Type: CNAME
Name: nepse
Value: <storage-name>.z12.web.core.windows.net
TTL: 3600
```

### 2. Verify DNS
```bash
nslookup nepse.sijanpaudel.com.np
```

### 3. Bind Domain (Optional - No SSL without CDN)
```bash
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
az storage account update \
  --name $STORAGE_NAME \
  --resource-group rg-nepse \
  --custom-domain nepse.sijanpaudel.com.np
```

---

## 🔒 Enable SSL (Optional - Costs $2-3/month)

### Quick Method
```bash
RG="rg-nepse"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)

# Create CDN
az cdn profile create -n nepse-cdn -g $RG --sku Standard_Microsoft -l koreacentral
az cdn endpoint create -n nepse --profile-name nepse-cdn -g $RG \
  --origin $STORAGE_NAME.z12.web.core.windows.net \
  --origin-host-header $STORAGE_NAME.z12.web.core.windows.net

# Update DNS to: nepse → nepse.azureedge.net

# Add custom domain (after DNS propagates)
az cdn custom-domain create --endpoint-name nepse --profile-name nepse-cdn -g $RG \
  --name nepse-custom --hostname nepse.sijanpaudel.com.np

# Enable SSL (takes 6-8 hours)
az cdn custom-domain enable-https --endpoint-name nepse --profile-name nepse-cdn -g $RG \
  --name nepse-custom --min-tls-version 1.2
```

---

## 🔄 Update After Code Changes

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./update-frontend.sh
```

---

## 📊 Monitor & Check Status

### Backend Logs
```bash
az containerapp logs show -n nepse-api -g rg-nepse --follow
```

### Frontend URL
```bash
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
az storage account show -n $STORAGE_NAME -g rg-nepse -q "primaryEndpoints.web" -o tsv
```

### SSL Status (if using CDN)
```bash
az cdn custom-domain show --endpoint-name nepse --profile-name nepse-cdn -g rg-nepse \
  --name nepse-custom -q "{Domain:hostName, SSL:customHttpsProvisioningState}"
```

### Cost Check
```bash
az costmanagement query \
  --scope "/subscriptions/$(az account show --query id -o tsv)" \
  --type Usage --timeframe MonthToDate
```

---

## 🔧 Troubleshooting

### Site Not Loading
```bash
# Check if storage website is enabled
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
az storage blob service-properties show --account-name $STORAGE_NAME --auth-mode login
```

### Backend API Not Responding
```bash
# Restart API
az containerapp revision restart -n nepse-api -g rg-nepse
```

### Clear CDN Cache
```bash
az cdn endpoint purge -n nepse --profile-name nepse-cdn -g rg-nepse --content-paths "/*"
```

---

## 💰 Current Cost Estimate

| Service | Monthly Cost |
|---------|-------------|
| Storage Static Website | $0.50 |
| Container Apps (backend) | $5-8 |
| Container Registry | $5 |
| CDN (optional for SSL) | $2-3 |
| **Total** | **$10-16/mo** |

**Without SSL:** $10-13/mo = 7-8 months  
**With SSL:** $15-16/mo = 6-7 months

---

## 🗑️ Delete Everything

```bash
az group delete -n rg-nepse --yes --no-wait
```

---

## 📝 File Reference

| File | Purpose |
|------|---------|
| `deploy-frontend-storage.sh` | Initial frontend deployment |
| `update-frontend.sh` | Redeploy after code changes |
| `docs/guides/AZURE_DEPLOYMENT_COMPLETE_GUIDE.md` | Full backend guide |
| `docs/guides/AZURE_STORAGE_CDN_SSL.md` | SSL setup guide |
