# 🚀 Quick Fix Guide

## Issue 1: Frontend Not Connecting to Backend

### Solution: Fix CORS

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./fix-cors.sh
```

Wait 30 seconds, then refresh your frontend. It should now connect to the backend!

### If Still Not Working

See: `docs/guides/BACKEND_CONNECTION_FIX.md` for detailed troubleshooting.

---

## Issue 2: Setup CI/CD (Auto-Deploy on Git Push)

### Step 1: Generate GitHub Secrets

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse
./setup-github-secrets.sh
```

This will output 3 secrets that you need to add to GitHub.

### Step 2: Add Secrets to GitHub

1. Go to: https://github.com/sijanpaudel14/Nepse/settings/secrets/actions
2. Click **"New repository secret"**
3. Add these 3 secrets (from script output):
   - `AZURE_CREDENTIALS` (full JSON)
   - `ACR_NAME` (e.g., `nepseacr123456`)
   - `STORAGE_ACCOUNT_NAME` (e.g., `nepsestorage12345678`)

### Step 3: Push to GitHub

```bash
git push origin main
```

**Done!** From now on:
- Push to `nepse_ai_trading/` → Auto-deploys backend
- Push to `nepse-saas-frontend/` → Auto-deploys frontend

---

## Verify Everything Works

### 1. Test Backend
```bash
BACKEND_URL=$(az containerapp show -n nepse-api -g rg-nepse -q "properties.configuration.ingress.fqdn" -o tsv)
curl https://$BACKEND_URL/health
# Should return: {"status":"ok"}
```

### 2. Test Frontend
```bash
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
FRONTEND_URL=$(az storage account show -n $STORAGE_NAME -g rg-nepse -q "primaryEndpoints.web" -o tsv)
echo "Frontend: $FRONTEND_URL"
# Open in browser
```

### 3. Test GitHub Actions
```bash
# Make a test change
echo "# Test" >> README.md
git add .
git commit -m "test: Trigger CI/CD"
git push origin main

# Go to: https://github.com/sijanpaudel14/Nepse/actions
# Watch the deployment happen automatically!
```

---

## 📚 Full Documentation

- **CI/CD Setup:** `docs/guides/GITHUB_ACTIONS_SETUP.md`
- **CORS Troubleshooting:** `docs/guides/BACKEND_CONNECTION_FIX.md`
- **Azure Deployment:** `docs/guides/AZURE_DEPLOYMENT_COMPLETE_GUIDE.md`
- **Quick Commands:** `docs/guides/AZURE_QUICK_COMMANDS.md`

---

## 🎯 Summary

| Task | Command | Time |
|------|---------|------|
| Fix CORS | `./fix-cors.sh` | 30 sec |
| Setup CI/CD Secrets | `./setup-github-secrets.sh` | 2 min |
| Add Secrets to GitHub | (Manual in browser) | 3 min |
| Push & Deploy | `git push origin main` | 5 min |

**Total:** ~10 minutes to fully automate your deployment! 🚀
