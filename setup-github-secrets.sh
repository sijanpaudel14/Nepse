#!/bin/bash
# =============================================================================
# GitHub Actions Setup Helper
# Generates all secrets needed for CI/CD
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   GitHub Actions Setup Helper${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

RG="rg-nepse"

# Step 1: Get Subscription ID
echo -e "${GREEN}[1/4]${NC} Getting Azure Subscription..."
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
echo "✓ Subscription: $SUBSCRIPTION_NAME"
echo "  ID: $SUBSCRIPTION_ID"

# Step 2: Create Service Principal
echo -e "\n${GREEN}[2/4]${NC} Creating Service Principal for GitHub Actions..."
echo "  (This gives GitHub permission to deploy)"

SP_OUTPUT=$(az ad sp create-for-rbac \
  --name "github-actions-nepse-$(date +%s)" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG \
  --sdk-auth 2>/dev/null)

echo "✓ Service Principal created"

# Step 3: Get Resource Names
echo -e "\n${GREEN}[3/4]${NC} Getting Azure resource names..."

ACR_NAME=$(az acr list -g $RG --query "[0].name" -o tsv 2>/dev/null || echo "")
if [ -z "$ACR_NAME" ]; then
    echo "  ⚠ Warning: ACR not found. Create it first."
    ACR_NAME="<YOUR_ACR_NAME>"
fi

STORAGE_NAME=$(cat /tmp/nepse-storage-name 2>/dev/null || echo "")
if [ -z "$STORAGE_NAME" ]; then
    STORAGE_NAME=$(az storage account list -g $RG --query "[0].name" -o tsv 2>/dev/null || echo "")
fi
if [ -z "$STORAGE_NAME" ]; then
    echo "  ⚠ Warning: Storage account not found. Deploy frontend first."
    STORAGE_NAME="<YOUR_STORAGE_NAME>"
fi

echo "✓ ACR Name: $ACR_NAME"
echo "✓ Storage Name: $STORAGE_NAME"

# Step 4: Display Secrets
echo -e "\n${GREEN}[4/4]${NC} GitHub Secrets to Add:"
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}AZURE_CREDENTIALS${NC}"
echo -e "${BLUE}================================================${NC}"
echo "$SP_OUTPUT"
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}ACR_NAME${NC}"
echo -e "${BLUE}================================================${NC}"
echo "$ACR_NAME"
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${YELLOW}STORAGE_ACCOUNT_NAME${NC}"
echo -e "${BLUE}================================================${NC}"
echo "$STORAGE_NAME"
echo ""

# Save to file
SECRETS_FILE="/tmp/github-secrets-nepse.txt"
cat > $SECRETS_FILE << EOF
# GitHub Secrets for NEPSE CI/CD
# Add these at: https://github.com/sijanpaudel14/Nepse/settings/secrets/actions

1. AZURE_CREDENTIALS
-------------------
$SP_OUTPUT

2. ACR_NAME
-------------------
$ACR_NAME

3. STORAGE_ACCOUNT_NAME
-------------------
$STORAGE_NAME
EOF

echo -e "${GREEN}✓ Secrets saved to: $SECRETS_FILE${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Go to: https://github.com/sijanpaudel14/Nepse/settings/secrets/actions"
echo "2. Click 'New repository secret'"
echo "3. Add the 3 secrets shown above"
echo "4. Push code to GitHub to trigger deployment"
echo ""
echo "See: docs/guides/GITHUB_ACTIONS_SETUP.md for detailed instructions"
