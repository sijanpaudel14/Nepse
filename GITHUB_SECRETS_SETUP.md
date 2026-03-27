# GitHub Secrets Setup for CI/CD

The GitHub Actions workflows require the following secrets to deploy automatically.

## Required Secrets

### 1. Vercel Deployment (Frontend)

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

Add these 3 secrets:

| Secret Name | Value | How to Get |
|------------|-------|------------|
| `VERCEL_TOKEN` | `vercel_xxxx...` | 1. Go to https://vercel.com/account/tokens<br>2. Create token named "GitHub Actions"<br>3. Copy the token |
| `VERCEL_ORG_ID` | `team_M6QJl9NGHOuIJSJMCxu2cijU` | Already found (see below) |
| `VERCEL_PROJECT_ID` | `prj_oJZndx2JxvGsm6RNJ0GAuuATb8t3` | Already found (see below) |

**Your Project Info:**
```json
{
  "projectId": "prj_oJZndx2JxvGsm6RNJ0GAuuATb8t3",
  "orgId": "team_M6QJl9NGHOuIJSJMCxu2cijU",
  "projectName": "nepse-saas-frontend"
}
```

### 2. Azure Deployment (Backend - Already Set Up)

These should already exist in your GitHub repo:

- `AZURE_CREDENTIALS` (for Azure CLI login)
- `ACR_USERNAME` (Azure Container Registry)
- `ACR_PASSWORD` (Azure Container Registry)

---

## How to Add Secrets

1. Go to: https://github.com/sijanpaudel14/Nepse/settings/secrets/actions
2. Click **"New repository secret"**
3. Enter **Name** and **Secret** (paste the value)
4. Click **"Add secret"**
5. Repeat for all 3 Vercel secrets

---

## Testing the Workflow

After adding secrets:

1. Make any change to frontend code
2. Commit and push to `main` branch
3. Go to: https://github.com/sijanpaudel14/Nepse/actions
4. Watch the "Deploy Frontend to Vercel" workflow run
5. If successful, changes auto-deploy to https://nepse.sijanpaudel.com.np

---

## Troubleshooting

**If workflow fails:**
- Check that all 3 secrets are added correctly
- Verify the token has "Deploy" permissions in Vercel
- Check workflow logs for specific error messages

**Manual deploy (bypass CI/CD):**
```bash
cd nepse-saas-frontend
vercel --prod
```
