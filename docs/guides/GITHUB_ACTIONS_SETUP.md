# 🔄 GitHub Actions CI/CD Setup Guide

## Overview

Automated deployment pipeline that:
- ✅ Builds and deploys backend when you push to `nepse_ai_trading/`
- ✅ Builds and deploys frontend when you push to `nepse-saas-frontend/`
- ✅ Can be triggered manually from GitHub Actions tab

---

## Step 1: Create Azure Service Principal

This gives GitHub Actions permission to deploy to your Azure subscription.

```bash
# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "Subscription ID: $SUBSCRIPTION_ID"

# Create service principal with Contributor role
az ad sp create-for-rbac \
  --name "github-actions-nepse" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/rg-nepse \
  --sdk-auth
```

**Copy the entire JSON output!** It looks like:
```json
{
  "clientId": "xxx",
  "clientSecret": "xxx",
  "subscriptionId": "xxx",
  "tenantId": "xxx",
  ...
}
```

---

## Step 2: Get Azure Resource Names

```bash
# Get ACR name
ACR_NAME=$(az acr list -g rg-nepse --query "[0].name" -o tsv)
echo "ACR Name: $ACR_NAME"

# Get Storage account name
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
echo "Storage Name: $STORAGE_NAME"

# Copy these values!
```

---

## Step 3: Add GitHub Secrets

1. Go to your GitHub repository: `https://github.com/sijanpaudel14/Nepse`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these secrets:

| Secret Name | Value | Where to Get It |
|-------------|-------|-----------------|
| `AZURE_CREDENTIALS` | Entire JSON from Step 1 | Copy full JSON output |
| `ACR_NAME` | `nepseacrXXXXXX` | From Step 2 |
| `STORAGE_ACCOUNT_NAME` | `nepsesstorageXXXXXXXX` | From Step 2 or `/tmp/nepse-storage-name` |

### Adding Secrets (Step-by-Step):

1. **AZURE_CREDENTIALS:**
   - Name: `AZURE_CREDENTIALS`
   - Secret: Paste the full JSON from Step 1
   - Click "Add secret"

2. **ACR_NAME:**
   - Name: `ACR_NAME`
   - Secret: Your ACR name (e.g., `nepseacr123456`)
   - Click "Add secret"

3. **STORAGE_ACCOUNT_NAME:**
   - Name: `STORAGE_ACCOUNT_NAME`
   - Secret: Your storage name (e.g., `nepsestorage12345678`)
   - Click "Add secret"

---

## Step 4: Push Workflows to GitHub

```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse

# Add workflow files
git add .github/workflows/

# Commit
git commit -m "ci: Add GitHub Actions workflows for auto-deployment"

# Push to GitHub
git push origin main
```

---

## Step 5: Test the Pipeline

### Method 1: Push Code Changes

```bash
# Make a small change to backend
cd nepse_ai_trading
echo "# Test change" >> README.md
git add .
git commit -m "test: Trigger backend deployment"
git push origin main
```

Go to GitHub → Actions tab → Watch the **"Deploy Backend to Azure"** workflow run!

### Method 2: Manual Trigger

1. Go to GitHub → **Actions** tab
2. Select **"Deploy Backend to Azure"** or **"Deploy Frontend to Azure"**
3. Click **"Run workflow"** → **"Run workflow"** button
4. Watch it deploy!

---

## Step 6: Verify Deployment

### Check GitHub Actions

1. Go to **Actions** tab in GitHub
2. Click on the running workflow
3. Watch the logs in real-time
4. Should see ✅ green checkmarks when successful

### Check Deployed Apps

```bash
# Backend URL
az containerapp show -n nepse-api -g rg-nepse -q "properties.configuration.ingress.fqdn" -o tsv

# Frontend URL
az storage account show -n $STORAGE_NAME -g rg-nepse -q "primaryEndpoints.web" -o tsv
```

---

## Workflow Triggers

| File Path Changed | Workflow Triggered |
|-------------------|-------------------|
| `nepse_ai_trading/**` | Deploy Backend |
| `nepse-saas-frontend/**` | Deploy Frontend |
| `.github/workflows/deploy-backend.yml` | Deploy Backend |
| `.github/workflows/deploy-frontend.yml` | Deploy Frontend |
| `docs/**`, `README.md`, etc. | Nothing (saves Actions minutes) |

---

## Troubleshooting

### "Azure Login Failed"

**Cause:** `AZURE_CREDENTIALS` secret is wrong or expired.

**Fix:**
```bash
# Recreate service principal
az ad sp create-for-rbac \
  --name "github-actions-nepse" \
  --role Contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)/resourceGroups/rg-nepse \
  --sdk-auth

# Update the AZURE_CREDENTIALS secret in GitHub
```

### "ACR Not Found"

**Cause:** `ACR_NAME` secret is wrong.

**Fix:**
```bash
# Get correct ACR name
az acr list -g rg-nepse --query "[0].name" -o tsv

# Update ACR_NAME secret in GitHub
```

### "Storage Account Not Found"

**Cause:** `STORAGE_ACCOUNT_NAME` secret is wrong.

**Fix:**
```bash
# Get correct storage name
cat /tmp/nepse-storage-name

# Or list storage accounts
az storage account list -g rg-nepse --query "[0].name" -o tsv

# Update STORAGE_ACCOUNT_NAME secret in GitHub
```

### "Docker Build Failed"

**Cause:** Backend code has errors.

**Fix:**
1. Check the error in GitHub Actions logs
2. Fix the code locally
3. Test locally: `cd nepse_ai_trading && docker build -t nepse-api:test .`
4. Push fix to GitHub

### "Build Failed - yarn install"

**Cause:** Frontend dependencies issue.

**Fix:**
1. Check the error in GitHub Actions logs
2. Test locally: `cd nepse-saas-frontend && yarn install && BUILD_MODE=static yarn build`
3. Push fix to GitHub

---

## Advanced: Deployment Badges

Add status badges to your README:

```markdown
![Backend Deploy](https://github.com/sijanpaudel14/Nepse/actions/workflows/deploy-backend.yml/badge.svg)
![Frontend Deploy](https://github.com/sijanpaudel14/Nepse/actions/workflows/deploy-frontend.yml/badge.svg)
```

---

## Cost of GitHub Actions

- **Free tier:** 2,000 minutes/month for private repos
- **Each deployment:** ~5-10 minutes
- **Your usage:** ~200 deployments/month = FREE ✅

---

## Manual Deployment (Backup Method)

If GitHub Actions fails, you can still deploy manually:

```bash
# Backend
cd nepse_ai_trading
docker build -t nepse-api:manual .
docker tag nepse-api:manual $ACR_NAME.azurecr.io/nepse-api:manual
az acr login -n $ACR_NAME
docker push $ACR_NAME.azurecr.io/nepse-api:manual
az containerapp update -n nepse-api -g rg-nepse --image $ACR_NAME.azurecr.io/nepse-api:manual

# Frontend
cd ../nepse-saas-frontend
BUILD_MODE=static yarn build
az storage blob upload-batch --account-name $STORAGE_NAME --auth-mode login -d '$web' -s ./out --overwrite
```

---

## Next Steps

1. ✅ Push code changes to GitHub
2. ✅ Watch GitHub Actions deploy automatically
3. ✅ Verify deployments at your URLs
4. 🎉 Profit!

**No more manual deployments needed!** 🚀
