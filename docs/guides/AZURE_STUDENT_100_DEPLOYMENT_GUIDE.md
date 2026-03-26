# Azure Student $100 Deployment Guide for NEPSE Project

## Goal

This guide helps you deploy your full project from start to end with Azure Student credit, keep monthly cost low, and connect:

- nepse.sijanpaudel.com.np (frontend)
- nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io (backend)

It is written for a complete beginner.

---

## 1) Best Architecture for 7 to 8 Month Target

### Recommended ultra-budget architecture

1. Frontend: Azure Static Web Apps (Free plan)
2. Backend API: Azure Container Apps (Consumption plan)
3. Database: SQLite on Azure Files mount (very low cost)
4. Container Image: GHCR (GitHub Container Registry) to avoid ACR monthly charge
5. Domain DNS: Your domain provider for sijanpaudel.com.np

### Why this is best for $100 credit and long duration

1. Static Web Apps free tier can host frontend at near-zero cost
2. Container Apps consumption can scale down and stay cheap for low traffic
3. SQLite + Azure Files avoids PostgreSQL fixed monthly costs
4. GHCR avoids ACR Basic monthly cost
5. Better for long credit life than two always-on App Services

### Monthly budget target (strict)

To stretch $100 for 7 to 8 months, keep Azure spend around:

- $12 to $14 per month max

At this spend, $100 can last about 7 to 8 months.

---

## 2) Cost Planning Before You Start

These are rough estimates and vary by region.

1. Static Web Apps Free: about $0/month
2. Container Apps consumption (light traffic, min replicas 0): about $3 to $10/month
3. Azure Files (small SQLite DB + logs): about $1 to $4/month
4. Log Analytics (if not controlled): $0 to $5/month
5. GHCR: usually $0 for this use case

Estimated total for light usage:

- Around $4 to $14/month

With $100 credit, this can last roughly 7 to 8 months if you keep logs and scaling controlled.

Important: Always use Cost Management alerts from Day 1.

---

## 3) Prerequisites Checklist

Before starting, make sure you have:

1. Azure account with Student subscription active
2. GitHub account
3. DNS access for sijanpaudel.com.np
4. Local tools installed:
   - Git
   - Docker Desktop
   - Azure CLI

Verify local tools:

    git --version
    docker --version
    az --version

Login to Azure:

    az login

Select your student subscription:

    az account list --output table
    az account set --subscription "YOUR_STUDENT_SUBSCRIPTION_NAME_OR_ID"

---

## 4) Prepare Your Repository

From your project root, ensure both folders are committed:

- nepse-saas-frontend
- nepse_ai_trading

If needed:

    cd "/run/media/sijanpaudel/New Volume/Nepse"
    git add .
    git commit -m "prepare azure deployment"
    git push origin main

---

## 5) Create Azure Resource Group

Choose one region and keep all resources there.

Example:

    az group create --name rg-nepse-student --location centralindia

---

## 6) Use GitHub Container Registry (No ACR Cost)

We avoid ACR to save around $5/month.

Build and push image to GHCR from local:

1. Create a GitHub Personal Access Token with package write permission
2. Login to GHCR:

   echo YOUR_GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin

3. Build image:

   cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
   docker build -t ghcr.io/YOUR_GITHUB_USERNAME/nepse-api:1.0 .

4. Push image:

   docker push ghcr.io/YOUR_GITHUB_USERNAME/nepse-api:1.0

---

## 7) Build and Push Backend Image

If you prefer Azure-only build, you can still use ACR later.
For 7 to 8 month budget target, continue with GHCR path.

---

## 8) Create Storage Account and Azure Files (for SQLite persistence)

This replaces PostgreSQL to reduce fixed monthly cost.

Create storage account:

az storage account create --name stnepsestudent123 --resource-group rg-nepse-student --location centralindia --sku Standard_LRS

Create file share:

az storage share-rm create --storage-account stnepsestudent123 --name nepse-data --resource-group rg-nepse-student

Get storage account key:

az storage account keys list --account-name stnepsestudent123 --resource-group rg-nepse-student --query "[0].value" -o tsv

Save this key safely. You will use it in Container Apps.

Database URL for SQLite in mounted volume:

sqlite:////mnt/data/nepse.db

---

## 9) Create Container Apps Environment

Create environment:

    az containerapp env create \
      --name cae-nepse-student \
      --resource-group rg-nepse-student \
      --location centralindia

---

## 10) Deploy Backend to Azure Container Apps (GHCR + Azure Files)

Create backend app from your GHCR image:

    az containerapp create \
      --name nepse-api \
      --resource-group rg-nepse-student \
      --environment cae-nepse-student \

--image ghcr.io/YOUR_GITHUB_USERNAME/nepse-api:1.0 \
 --target-port 8000 \
 --ingress external \
 --registry-server ghcr.io \
 --min-replicas 0 \
 --max-replicas 1

Set GHCR credentials:

    az containerapp registry set \

--name nepse-api \
 --resource-group rg-nepse-student \
 --server ghcr.io \
 --username YOUR_GITHUB_USERNAME \
 --password YOUR_GITHUB_PAT

Attach Azure Files to Container App environment:

    az containerapp env storage set \

--name cae-nepse-student \
 --resource-group rg-nepse-student \
 --storage-name nepsefiles \
 --azure-file-account-name stnepsestudent123 \
 --azure-file-account-key YOUR_STORAGE_ACCOUNT_KEY \
 --azure-file-share-name nepse-data \
 --access-mode ReadWrite

Mount storage to backend at /mnt/data:

    az containerapp update \

--name nepse-api \
 --resource-group rg-nepse-student \
 --yaml ./containerapp-nepse-api.yaml

Create this file at nepse_ai_trading/containerapp-nepse-api.yaml and use it in the update command:

      properties:
         template:
            containers:
               - name: nepse-api
                  volumeMounts:
                     - volumeName: nepsefiles
                        mountPath: /mnt/data
            volumes:
               - name: nepsefiles
                  storageName: nepsefiles
                  storageType: AzureFile

Set backend environment variables:

    az containerapp update \
      --name nepse-api \
      --resource-group rg-nepse-student \
      --set-env-vars \
      DATABASE_URL="sqlite:////mnt/data/nepse.db" \
      OPENAI_API_KEY="YOUR_OPENAI_KEY" \
      TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN" \
      TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID" \
      LOG_LEVEL="INFO"

Optional but recommended: reduce log ingestion cost by keeping only needed diagnostics.

Get backend default URL:

    az containerapp show --name nepse-api --resource-group rg-nepse-student --query properties.configuration.ingress.fqdn -o tsv

Test health endpoint:

    https://YOUR_BACKEND_FQDN/health

---

## 11) Deploy Frontend to Azure Static Web Apps

Use Azure Portal (easiest for beginner):

1. Create Resource -> Static Web App
2. Resource group: rg-nepse-student
3. Name: nepse-frontend
4. Hosting plan: Free
5. Source: GitHub
6. Repository: your repo
7. Branch: main
8. Build details:
   - App location: nepse-saas-frontend
   - API location: leave empty
   - Output location: .next

After creation, GitHub Actions will build and deploy automatically.

Important app setting in Static Web Apps:

1. Open Static Web App
2. Configuration -> Application settings
3. Add:
   - NEXT_PUBLIC_API_URL = https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io

Redeploy frontend after setting env variable.

---

## 12) Domain Setup (Your Main Requirement)

You want:

- nepse.sijanpaudel.com.np -> frontend
- nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io -> backend

### 12.1 Frontend custom domain

In Static Web App:

1. Custom domains -> Add
2. Enter nepse.sijanpaudel.com.np
3. Azure shows DNS records to add

In your DNS provider, add the shown records (usually CNAME + TXT verification).

Typical pattern:

1. CNAME
   - Host: nepse
   - Value: YOUR_STATIC_WEB_APP_HOSTNAME
2. TXT (verification)
   - Host: asuid.nepse
   - Value: value from Azure

### 12.2 Backend custom domain

In Container App for backend:

1. Open Container App nepse-api
2. Custom domains -> Add
3. Enter nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io

Add DNS records in domain provider (Azure shows exact values):

1. CNAME
   - Host: api.nepse
   - Value: YOUR_CONTAINER_APP_FQDN
2. TXT verification record

---

## 13) HTTPS and SSL

1. Static Web Apps usually handles managed SSL automatically after domain validation
2. Container Apps supports managed certificates once domain is verified
3. Ensure both URLs open with https and no warnings

Final URLs to test:

1. https://nepse.sijanpaudel.com.np
2. https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io/health

---

## 14) Critical Production Fixes in Your Code

You should apply these before going fully public:

1. CORS restriction in backend
   - Allow only https://nepse.sijanpaudel.com.np in production
   - Do not keep wildcard origin in production

2. Frontend API URL
   - Ensure NEXT_PUBLIC_API_URL is set in Azure
   - Never rely on localhost fallback in production

3. Secrets
   - Keep OPENAI and TELEGRAM tokens only in Azure environment variables
   - Never commit secrets to GitHub

---

## 15) Cost Protection (Very Important)

Do this immediately to protect your $100 credit.

1. Create budget in Cost Management
   - Budget name: nepse-student-budget
   - Amount: $12 monthly target alert, $14 monthly hard alert
2. Set alert emails at 50%, 80%, 100% of monthly budget
3. Keep backend min replicas at 0
4. Keep max replicas at 1 unless absolutely needed
5. Avoid PostgreSQL unless you outgrow SQLite
6. Avoid ACR unless GHCR is not suitable
7. Keep log retention low (for example 7 days)
8. Delete unused resources immediately

---

## 16) Daily Deployment Workflow

When you update code:

Frontend:

1. Commit and push to main
2. GitHub Action redeploys Static Web App automatically

Backend:

1. Build new image tag:

   docker build -t ghcr.io/YOUR_GITHUB_USERNAME/nepse-api:1.1 .
   docker push ghcr.io/YOUR_GITHUB_USERNAME/nepse-api:1.1

2. Update container app image:

   az containerapp update \
    --name nepse-api \
    --resource-group rg-nepse-student \
    --image ghcr.io/YOUR_GITHUB_USERNAME/nepse-api:1.1

3. Re-test health endpoint and frontend actions

---

## 17) End-to-End Testing Checklist

1. Frontend loads at nepse.sijanpaudel.com.np
2. Backend health returns success at nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io/health
3. Frontend API calls hit backend domain (check browser network tab)
4. No CORS errors
5. No mixed content errors
6. Key features work:
   - scan
   - analyze
   - telegram alerts
7. Check Azure logs for errors

---

## 18) Troubleshooting Quick Fixes

### Problem: Domain not validating

1. Wait 10 to 30 minutes for DNS propagation
2. Recheck CNAME host and value
3. Ensure TXT verification record is exact

### Problem: Frontend works but API fails

1. Check NEXT_PUBLIC_API_URL in Static Web App settings
2. Check backend ingress is external
3. Check backend /health endpoint directly
4. Check CORS allowed origins

### Problem: Backend crash on startup

1. Verify DATABASE_URL is correct
2. If using SQLite, verify storage mount path exists (/mnt/data)
3. Check container app logs:

   az containerapp logs show --name nepse-api --resource-group rg-nepse-student --follow

### Problem: Credit draining fast

1. Lower max replicas
2. Confirm frontend is on free Static Web App plan
3. Confirm you are not paying for ACR (use GHCR)
4. Reduce log retention and disable unnecessary diagnostics
5. Remove unused resources from resource group

---

## 19) What To Do First Right Now

If you want immediate progress, do these 5 actions today:

1. Create resource group
2. Create ACR
3. Build and push backend image
4. Create Container App backend and test /health
5. Create Static Web App frontend and set NEXT_PUBLIC_API_URL

After that, do custom domains and SSL.

---

## 20) Final Notes for Beginner Success

1. Always change one thing at a time
2. Test after every major step
3. Keep a text file with all Azure names and passwords
4. Do not skip budget alerts
5. If stuck, check logs first, then fix

You can deploy this fully even as a beginner by following this guide in order.
