# ✅ Corrected Setup Guide

## Issue: Resource Group Name Was Wrong

**Fixed!** All scripts now use the correct resource group: `rg-nepse-trading`

---

## Your Current Status

✅ **Backend:** Running  
✅ **ACR:** Created (`nepseacr49878`)  
✅ **Frontend:** Deployed to Storage  
❌ **Frontend-Backend Connection:** Needs CORS fix  
❌ **CI/CD:** Needs GitHub secrets setup  

---

## Step 1: Fix Frontend Connection (CORS)

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./fix-cors.sh
```

**Wait 30 seconds**, then refresh your frontend. It should now connect to the backend!

---

## Step 2: Setup CI/CD

### 2.1: Generate GitHub Secrets

```bash
./setup-github-secrets.sh
```

This will output 3 secrets. **Copy them!**

### 2.2: Add Secrets to GitHub

1. Go to: https://github.com/sijanpaudel14/Nepse/settings/secrets/actions
2. Click **"New repository secret"**
3. Add these 3 secrets:

**Secret 1: AZURE_CREDENTIALS**
- Name: `AZURE_CREDENTIALS`
- Value: The full JSON output from script (starts with `{`)

**Secret 2: ACR_NAME**
- Name: `ACR_NAME`
- Value: `nepseacr49878` (your ACR name)

**Secret 3: STORAGE_ACCOUNT_NAME**
- Name: `STORAGE_ACCOUNT_NAME`  
- Value: Your storage name (from `/tmp/nepse-storage-name`)

To get your storage name:
```bash
cat /tmp/nepse-storage-name
```

### 2.3: Push to GitHub

```bash
git push origin main
```

---

## How It Works After Setup

### Automatic Deployment Triggers:

| Change | Result |
|--------|--------|
| Push to `nepse_ai_trading/**` | Backend auto-deploys |
| Push to `nepse-saas-frontend/**` | Frontend auto-deploys |
| Push to `docs/**` | Nothing (saves free minutes) |

### Manual Deployment:

1. Go to GitHub → **Actions** tab
2. Select workflow (Backend or Frontend)
3. Click **"Run workflow"**

---

## Verify Everything

### Check Backend
```bash
curl https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io/health
# Should return: {"status":"ok"}
```

### Check Frontend
```bash
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
echo "https://$STORAGE_NAME.z12.web.core.windows.net"
# Open in browser
```

### Check GitHub Actions
After pushing code, go to:
https://github.com/sijanpaudel14/Nepse/actions

You'll see workflows running automatically! 🚀

---

## Quick Reference

| Task | Command |
|------|---------|
| Fix CORS | `./fix-cors.sh` |
| Get GitHub Secrets | `./setup-github-secrets.sh` |
| Get ACR Name | `cat /tmp/nepse-acr-name` |
| Get Storage Name | `cat /tmp/nepse-storage-name` |
| Backend URL | `az containerapp show -n nepse-api -g rg-nepse-trading --query "properties.configuration.ingress.fqdn" -o tsv` |
| Frontend URL | `az storage account show -n $(cat /tmp/nepse-storage-name) -g rg-nepse-trading --query "primaryEndpoints.web" -o tsv` |

---

## Troubleshooting

### "Resource group not found"
All scripts now use `rg-nepse-trading`. If you see this error, pull latest code:
```bash
git pull origin main
```

### "ACR not found" in GitHub Actions
Make sure you added `ACR_NAME` secret with value: `nepseacr49878`

### "Storage account not found" in GitHub Actions
Get your storage name and add it as `STORAGE_ACCOUNT_NAME` secret:
```bash
cat /tmp/nepse-storage-name
```

---

## Cost Summary

| Service | Monthly Cost |
|---------|-------------|
| Storage Static Website | $0.50 |
| Container Apps (backend) | $5-8 |
| Container Registry | $5 |
| **Total** | **$10.50-13.50** |

**Budget:** $100/year = **~8 months** ✅

---

## Next Steps

1. ✅ Run `./fix-cors.sh` (30 sec)
2. ✅ Run `./setup-github-secrets.sh` (2 min)
3. ✅ Add 3 secrets to GitHub (3 min)
4. ✅ Push to GitHub: `git push origin main`
5. 🎉 Enjoy automated deployments!

**Everything is fixed and ready to go!** 🚀
