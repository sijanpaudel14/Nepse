#!/bin/bash
cd /run/media/sijanpaudel/New\ Volume/Nepse

RG="rg-nepse"
STORAGE_NAME="nepsestorage$(date +%s | tail -c 8)"

# Create storage
az storage account create -n $STORAGE_NAME -g $RG -l koreacentral --sku Standard_LRS --kind StorageV2
az storage blob service-properties update --account-name $STORAGE_NAME --static-website --index-document index.html --404-document 404.html

# Build frontend
cd nepse-saas-frontend
BACKEND_URL=$(az containerapp show -n nepse-api -g $RG -q "properties.configuration.ingress.fqdn" -o tsv)
echo "NEXT_PUBLIC_API_URL=https://$BACKEND_URL" > .env.production
BUILD_MODE=static yarn build

# Deploy
STORAGE_KEY=$(az storage account keys list -n $STORAGE_NAME -g $RG -q "[0].value" -o tsv)
az storage blob upload-batch --account-name $STORAGE_NAME --account-key $STORAGE_KEY -d '$web' -s ./out --overwrite

# Get URL
az storage account show -n $STORAGE_NAME -g $RG -q "primaryEndpoints.web" -o tsv