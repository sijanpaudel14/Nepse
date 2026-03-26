# Personalized Command Sheet (Azure Student 100 USD, 7 to 8 Month Plan)

Use this sheet in order. Run from terminal line by line.

## 0) Fill these values once

Replace only values on the right side:

```bash
# Azure basics
SUBSCRIPTION_ID="YOUR_AZURE_STUDENT_SUBSCRIPTION_ID"
LOCATION="southeastasia"
RG="rg-nepse-student"

# Domain
FRONTEND_DOMAIN="nepse.sijanpaudel.com.np"
API_DOMAIN="nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io"

# App names
CONTAINER_ENV="cae-nepse-student"
BACKEND_APP="nepse-api"

# Storage (must be globally unique)
STORAGE_ACCOUNT="stnepsestudent123"
FILE_SHARE="nepse-data"

# GitHub
GH_USER="YOUR_GITHUB_USERNAME"
GH_PAT="YOUR_GITHUB_PAT"
IMAGE="ghcr.io/${GH_USER}/nepse-api:1.0"

# Secrets
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID"
```

## 1) Login and select subscription

```bash
az login
az account set --subscription "$SUBSCRIPTION_ID"
az account show --output table
```

## 2) Create resource group

```bash
az group create --name "$RG" --location "$LOCATION"
```

## 3) Create storage account and file share (for SQLite persistence)

```bash
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS

az storage share-rm create \
  --storage-account "$STORAGE_ACCOUNT" \
  --resource-group "$RG" \
  --name "$FILE_SHARE"

STORAGE_KEY=$(az storage account keys list \
  --account-name "$STORAGE_ACCOUNT" \
  --resource-group "$RG" \
  --query "[0].value" -o tsv)

echo "Storage key loaded into STORAGE_KEY"
```

## 4) Push backend image to GHCR (no ACR monthly cost)

```bash
echo "$GH_PAT" | docker login ghcr.io -u "$GH_USER" --password-stdin

cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
docker build -t "$IMAGE" .
docker push "$IMAGE"
```

## 5) Create Container Apps environment

```bash
az containerapp env create \
  --name "$CONTAINER_ENV" \
  --resource-group "$RG" \
  --location "$LOCATION"
```

## 6) Register Azure Files storage with Container Apps environment

```bash
az containerapp env storage set \
  --name "$CONTAINER_ENV" \
  --resource-group "$RG" \
  --storage-name nepsefiles \
  --azure-file-account-name "$STORAGE_ACCOUNT" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$FILE_SHARE" \
  --access-mode ReadWrite
```

## 7) Create backend Container App

```bash
az containerapp create \
  --name "$BACKEND_APP" \
  --resource-group "$RG" \
  --environment "$CONTAINER_ENV" \
  --image "$IMAGE" \
  --target-port 8000 \
  --ingress external \
  --registry-server ghcr.io \
  --registry-username "$GH_USER" \
  --registry-password "$GH_PAT" \
  --min-replicas 0 \
  --max-replicas 1 \
  --env-vars \
    # NEPSE AI Trading Bot - Environment Variables
    # =============================================
```

## 8) Mount Azure Files at /mnt/data

Create file:

Path: /run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading/containerapp-nepse-api.yaml

Content:

```yaml
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
```

Apply it:

```bash
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
az containerapp update \
  --name "$BACKEND_APP" \
  --resource-group "$RG" \
  --yaml ./containerapp-nepse-api.yaml
```

## 9) Get backend URL and test health

```bash
BACKEND_FQDN=$(az containerapp show \
  --name "$BACKEND_APP" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn -o tsv)

echo "https://${BACKEND_FQDN}/health"
```

Open in browser and verify healthy response.

## 10) Frontend deployment (Static Web Apps Free)

Use Azure Portal:

1. Create Static Web App (Free)
2. Connect GitHub repo
3. App location: nepse-saas-frontend
4. Build output: .next
5. Add app setting NEXT_PUBLIC_API_URL = https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io

## 11) Domain mapping

Add custom domains in Azure:

1. Frontend: nepse.sijanpaudel.com.np
2. Backend: nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io

Azure will show CNAME and TXT records. Add those exact records in your DNS provider.

## 12) Monthly budget protection (required)

Use Azure Portal -> Cost Management -> Budgets:

1. Budget 1: 12 USD monthly (warning)
2. Budget 2: 14 USD monthly (critical)
3. Alert at 50 percent, 80 percent, 100 percent

Keep max replicas 1 and min replicas 0.

---

## Token and key source map (important)

You asked where to extract token from Azure. Use this map:

1. Azure login token:

- You do not manually copy this.
- Run az login and Azure CLI handles it automatically.

2. Azure Storage Account key (required here):

- Azure Portal path:
  Storage accounts -> stnepsestudent123 -> Security + networking -> Access keys
- Copy key1 value
- Or fetch by CLI command in Step 3 (recommended)

3. GitHub token (GH_PAT, not from Azure):

- GitHub path:
  GitHub -> Settings -> Developer settings -> Personal access tokens -> Tokens (classic)
- Create token with scopes: write:packages, read:packages, repo

4. OpenAI key (not from Azure):

- OpenAI dashboard -> API keys

5. Telegram bot token (not from Azure):

- Telegram BotFather -> create bot -> token shown there

6. Telegram chat ID (not from Azure):

- Send message to your bot and get chat id via bot updates endpoint

---

## Quick update command when backend code changes

```bash
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse_ai_trading"
docker build -t "$IMAGE" .
docker push "$IMAGE"

az containerapp update \
  --name "$BACKEND_APP" \
  --resource-group "$RG" \
  --image "$IMAGE"
```
