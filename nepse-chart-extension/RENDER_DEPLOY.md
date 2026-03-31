# Deploying NEPSE Chart Analyzer Backend to Render

Complete step-by-step guide: GitHub repo → Render deployment → keep-alive cron.

---

## 1. Push to GitHub

### One-time setup (run these in your terminal)

```bash
cd "/run/media/sijanpaudel/New Volume/Nepse/nepse-chart-extension"

# Initialize git repo
git init
git add .
git commit -m "Initial commit — NEPSE Chart Analyzer"

# Create a new repo on github.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/nepse-chart-extension.git
git branch -M main
git push -u origin main
```

> On GitHub, go to **github.com → New repository** → name it `nepse-chart-extension` → **do NOT** check "Add README" → click Create. Then paste the remote commands above.

### Future pushes (after any code change)

```bash
git add .
git commit -m "describe what you changed"
git push
```

---

## 2. Deploy on Render

### 2a. Create account

Go to **[render.com](https://render.com)** → Sign up with GitHub (recommended — enables auto-deploys).

### 2b. Create Web Service

1. Dashboard → **New** → **Web Service**
2. Connect your GitHub account → select **nepse-chart-extension** repo
3. Fill in the form:

| Field | Value |
|---|---|
| **Name** | `nepse-chart-analyzer` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Free |

> The `render.yaml` in the repo root pre-fills most of these automatically.

4. Click **Create Web Service**.
5. Render builds and deploys. Takes 2–4 minutes first time.
6. Your URL will be: `https://nepse-chart-analyzer.onrender.com` (or similar)

### 2c. Test the deployment

```bash
curl https://nepse-chart-analyzer.onrender.com/health
# Expected: {"status":"ok","service":"nepse-chart-analyzer","version":"2.0"}
```

If you get a response — the backend is live.

---

## 3. Update the Extension to use Render URL

Open **`extension/background.js`** and change the `BACKEND_URL` constant at the top:

```js
// Change this line:
const BACKEND_URL = 'http://127.0.0.1:8000'

// To your Render URL:
const BACKEND_URL = 'https://nepse-chart-analyzer.onrender.com'
```

Then reload the extension in Chrome:
1. Go to `chrome://extensions/`
2. Find **NEPSE Pro Analyzer** → click the **refresh icon** (↺)
3. Reload any open NepseAlpha tab

Done — the extension now talks to Render instead of localhost.

---

## 4. Keep-Alive with GitHub Actions (Prevent Render Sleep)

Render free tier sleeps after **15 minutes of inactivity**. The workflow at
`.github/workflows/keep-alive.yml` pings the backend every 14 minutes.

### 4a. Add the Render URL as a GitHub Secret

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `RENDER_BACKEND_URL`
4. Value: `https://nepse-chart-analyzer.onrender.com` (your exact Render URL, **no trailing slash**)
5. Click **Add secret**

### 4b. Enable the workflow

The workflow file is already in `.github/workflows/keep-alive.yml`. Once pushed to GitHub, it runs automatically every 14 minutes.

To verify it's running:
- GitHub repo → **Actions** tab → **Keep Render alive** → see run history

### 4c. Manual test

GitHub repo → **Actions** → **Keep Render alive** → **Run workflow** → **Run workflow** (green button).

Check the run logs — you should see `Backend is alive ✓`.

---

## 5. Alternative Keep-Alive: cron-job.org (Recommended)

GitHub Actions free tier gives **2,000 minutes/month**. Running every 14 minutes = ~3,100 pings/month which exhausts free minutes by the end of the month.

**Better option: [cron-job.org](https://cron-job.org)** — free, unlimited, purpose-built.

1. Create free account at cron-job.org
2. **New cronjob** → fill in:

| Field | Value |
|---|---|
| URL | `https://nepse-chart-analyzer.onrender.com/health` |
| Schedule | Every 10 minutes |
| Request method | GET |
| Notifications | On failure only |

3. Save → Enable. Done.

No GitHub Actions minutes consumed. Use cron-job.org as the primary keep-alive and disable the GitHub Actions workflow (`keep-alive.yml`) in the Actions tab if needed.

---

## 6. Auto-Deploy on Code Changes

Because the repo is connected to Render via GitHub, any `git push` to `main` triggers an automatic redeploy. No manual steps needed after initial setup.

Deploy timeline:
- Push to GitHub → Render detects change → Rebuilds (~90 seconds) → New version live
- Zero downtime restart (Render keeps old instance running until new one is healthy)

---

## 7. Cold Start Warning

Even with keep-alive pinging, Render free tier has a **~30 second cold start** if it hasn't been hit for a while. The extension's 25-second timeout will show an error on the very first request after the backend wakes up. Just click **Retry** on the widget — the second request always works.

To avoid this entirely, upgrade to Render Starter plan ($7/month) which has no sleep.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Widget shows "Backend timed out" | Render is sleeping | Click Retry — backend wakes in ~30s |
| Health check returns 503 | Render is deploying | Wait 2 minutes and retry |
| Build failed on Render | Dependency issue | Check Render logs → Deploys tab |
| Extension still hits localhost | BACKEND_URL not updated | Edit background.js and reload extension |
| GitHub Actions not running | Workflow not pushed | `git add . && git commit && git push` |

### Check Render logs

Render Dashboard → your service → **Logs** tab. Look for:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000
```

---

## Summary

```
Your machine                  GitHub                  Render
─────────────                 ──────                  ──────────────────
git push ──────────────────→  repo       ──auto────→  nepse-backend live
background.js                 Actions    ──ping────→  /health every 14m
BACKEND_URL =                 (or cron-job.org)
  render.com/...
```
