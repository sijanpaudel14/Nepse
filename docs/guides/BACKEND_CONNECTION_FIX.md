# 🔧 Backend Connection Fix

## Issue: Frontend Can't Connect to Backend

### Common Causes & Fixes

#### 1. CORS Configuration

The backend CORS already allows all origins (`"*"`), but let's explicitly add your production domain:

**File:** `nepse_ai_trading/api/main.py` (around line 75)

Replace:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "*",
    ],
```

With:
```python
# Get frontend URL from environment
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        FRONTEND_URL,
        "https://*.z12.web.core.windows.net",  # Azure Storage
        "https://*.azureedge.net",  # Azure CDN
        "*",  # Fallback - remove in strict production
    ],
```

#### 2. Update Backend Environment Variable

```bash
# Get your storage URL
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
FRONTEND_URL="https://$STORAGE_NAME.z12.web.core.windows.net"

# Update Container App
az containerapp update \
  --name nepse-api \
  --resource-group rg-nepse \
  --set-env-vars "FRONTEND_URL=$FRONTEND_URL"

# Restart to apply changes
az containerapp revision restart \
  --name nepse-api \
  --resource-group rg-nepse
```

#### 3. Check Backend Health

```bash
# Test backend directly
BACKEND_URL=$(az containerapp show -n nepse-api -g rg-nepse -q "properties.configuration.ingress.fqdn" -o tsv)
curl https://$BACKEND_URL/health

# Should return: {"status":"ok"}
```

#### 4. Test API Endpoint

```bash
# Test a real endpoint
curl https://$BACKEND_URL/api/stocks

# Should return JSON with stock data
```

#### 5. Check Browser Console

Open your deployed frontend → Press F12 → Console tab

Look for errors like:
- `CORS policy` → Backend CORS issue
- `net::ERR_NAME_NOT_RESOLVED` → Wrong API URL
- `Failed to fetch` → Backend not running

#### 6. Verify Frontend API URL

Check the built files:
```bash
cd /run/media/sijanpaudel/New\ Volume/Nepse/nepse-saas-frontend
grep -r "NEXT_PUBLIC_API_URL" out/_next/static/chunks/
```

Should show: `https://nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io`

---

## Quick Fix Script

Run this to update backend CORS and restart:

```bash
#!/bin/bash
RG="rg-nepse"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)

# Update backend with frontend URL
az containerapp update \
  --name nepse-api \
  --resource-group $RG \
  --set-env-vars \
    "FRONTEND_URL=https://$STORAGE_NAME.z12.web.core.windows.net" \
    "CORS_ORIGINS=https://$STORAGE_NAME.z12.web.core.windows.net,http://localhost:3000"

# Restart
az containerapp revision restart -n nepse-api -g $RG

echo "✓ Backend updated and restarted"
echo "Wait 30 seconds, then test your frontend"
```

---

## Testing Checklist

After applying the fix:

1. **Wait 30 seconds** for backend to restart
2. **Open your frontend** in browser
3. **Press F12** → Network tab
4. **Refresh page**
5. **Check for API calls** to your backend
6. **Look for errors** in Console tab

---

## If Still Not Working

### Debug Steps:

```bash
# 1. Check backend logs
az containerapp logs show -n nepse-api -g rg-nepse --tail 50

# 2. Test backend directly from terminal
BACKEND_URL=$(az containerapp show -n nepse-api -g rg-nepse -q "properties.configuration.ingress.fqdn" -o tsv)
curl -v https://$BACKEND_URL/api/stocks

# 3. Check if backend is running
az containerapp show -n nepse-api -g rg-nepse -q "properties.runningStatus" -o tsv
# Should show: "Running"

# 4. Check frontend environment
cd nepse-saas-frontend/out
grep -A5 "NEXT_PUBLIC_API_URL" _next/static/chunks/*.js | head -20
```

### Common Issues:

| Error | Cause | Fix |
|-------|-------|-----|
| `CORS error` | Backend not allowing your domain | Update CORS config |
| `404 Not Found` | Wrong API path | Check route prefixes |
| `500 Server Error` | Backend crashed | Check logs with `az containerapp logs show` |
| `net::ERR_FAILED` | Backend not running | Restart with `az containerapp revision restart` |

---

## Need More Help?

Run this diagnostic script:

```bash
#!/bin/bash
echo "=== NEPSE Deployment Diagnostics ==="
echo ""

echo "1. Backend Status:"
az containerapp show -n nepse-api -g rg-nepse -q "{Status:properties.runningStatus, URL:properties.configuration.ingress.fqdn}"

echo ""
echo "2. Backend Health Check:"
BACKEND_URL=$(az containerapp show -n nepse-api -g rg-nepse -q "properties.configuration.ingress.fqdn" -o tsv)
curl -s https://$BACKEND_URL/health | jq .

echo ""
echo "3. Frontend URL:"
STORAGE_NAME=$(cat /tmp/nepse-storage-name)
az storage account show -n $STORAGE_NAME -g rg-nepse -q "primaryEndpoints.web" -o tsv

echo ""
echo "4. Environment Variables:"
az containerapp show -n nepse-api -g rg-nepse -q "properties.template.containers[0].env[*].{Name:name, Value:value}"
```

Save as `diagnose.sh`, make executable, and run!
