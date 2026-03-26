# 🚀 Deploy NEPSE Frontend to Azure (Policy Fix)

## Problem Solved
Azure Static Web Apps isn't available in your allowed regions. Using **Azure Storage Static Website** instead ($0.50/month).

---

## ⚡ Deploy Now (5 Minutes)

### Step 1: Make sure your backend is deployed
```bash
az containerapp show -n nepse-api -g rg-nepse-trading -q "properties.configuration.ingress.fqdn" -o tsv
```
If this shows a URL, your backend is ready ✅

### Step 2: Deploy Frontend
```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./deploy-frontend-storage.sh
```

**That's it!** Script will:
1. Create Azure Storage account
2. Enable static website hosting
3. Build your Next.js frontend
4. Upload to Azure
5. Give you the public URL

**Time:** ~5 minutes  
**Cost:** ~$0.50/month

---

## 🌐 Setup Custom Domain (nepse.sijanpaudel.com.np)

After deployment completes, the script will show you the storage URL. Example:
```
https://nepsestorage12345678.z12.web.core.windows.net
```

### Add DNS Record at Your Domain Registrar

```
Type: CNAME
Name: nepse
Value: nepsestorage12345678.z12.web.core.windows.net
TTL: 3600
```

**Note:** Without Azure CDN, custom domain will be HTTP only (no SSL). To add SSL, see below.

---

## 🔒 Optional: Enable SSL on Custom Domain

SSL requires Azure CDN (~$2-3/month extra). Follow this guide:
```bash
cat docs/guides/AZURE_STORAGE_CDN_SSL.md
```

Or run these commands:

```bash
RG="rg-nepse-trading"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)

# Create CDN
az cdn profile create -n nepse-cdn -g $RG --sku Standard_Microsoft -l koreacentral
az cdn endpoint create -n nepse --profile-name nepse-cdn -g $RG \
  --origin $STORAGE_NAME.z12.web.core.windows.net \
  --origin-host-header $STORAGE_NAME.z12.web.core.windows.net

# Update DNS to point to CDN
# CNAME  nepse  →  nepse.azureedge.net

# After DNS propagates (5-10 min), add custom domain
az cdn custom-domain create --endpoint-name nepse --profile-name nepse-cdn -g $RG \
  --name nepse-custom --hostname nepse.sijanpaudel.com.np

# Enable SSL (takes 6-8 hours to activate)
az cdn custom-domain enable-https --endpoint-name nepse --profile-name nepse-cdn -g $RG \
  --name nepse-custom --min-tls-version 1.2
```

---

## 🔄 Update After Code Changes

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./update-frontend.sh
```

This rebuilds and redeploys in ~2 minutes.

---

## 💰 Cost Summary

| Scenario | Monthly Cost | Duration on $100 |
|----------|-------------|------------------|
| **Basic (No SSL)** | $10.50 | ~9 months ✅ |
| **With SSL** | $15.50 | ~6 months |

**Breakdown:**
- Storage Static Website: $0.50
- Container Apps (backend): $5-8
- Container Registry: $5
- CDN + SSL (optional): $2-3

---

## 📚 More Guides

- **Full Azure Guide:** `docs/guides/AZURE_DEPLOYMENT_COMPLETE_GUIDE.md`
- **SSL Setup:** `docs/guides/AZURE_STORAGE_CDN_SSL.md`
- **Quick Commands:** `docs/guides/AZURE_QUICK_COMMANDS.md`

---

## ✅ Your Checklist

- [ ] Backend deployed (`az containerapp show -n nepse-api -g rg-nepse-trading`)
- [ ] Run `./deploy-frontend-storage.sh`
- [ ] Test the storage URL in browser
- [ ] Add DNS CNAME record for custom domain
- [ ] (Optional) Setup CDN for SSL
- [ ] Test both domains working

---

## 🆘 Troubleshooting

### Build Fails
```bash
cd nepse-saas-frontend
BUILD_MODE=static yarn build
# Check for errors
```

### Can't Find Storage Name
```bash
cat /tmp/nepse-storage-name
# If empty, redeploy: ./deploy-frontend-storage.sh
```

### Site Shows 404
```bash
# Check if files uploaded
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
az storage blob list --account-name $STORAGE_NAME --container-name '$web' --auth-mode login
```

---

**Ready?** Run: `./deploy-frontend-storage.sh` 🚀
