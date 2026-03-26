#!/usr/bin/env bash
set -euo pipefail

# One-shot VM deployment script for NEPSE frontend + backend on one Azure VM.
# Usage:
#   chmod +x deploy/vm/deploy-vm-nepse.sh
#   sudo bash deploy/vm/deploy-vm-nepse.sh
#
# Required env vars before running:
#   OPENAI_API_KEY
#   TELEGRAM_BOT_TOKEN
#   TELEGRAM_CHAT_ID
# Optional:
#   SHAREHUB_AUTH_TOKEN
#   SHAREHUB_AUTH_COOKIES

DOMAIN_FRONTEND="nepse.sijanpaudel.com.np"
DOMAIN_API="nepse-api.calmwater-c82ed95c.southeastasia.azurecontainerapps.io"
APP_ROOT="/opt/nepse"
BACKEND_DIR="$APP_ROOT/nepse_ai_trading"
FRONTEND_DIR="$APP_ROOT/nepse-saas-frontend"
BACKEND_VENV="$BACKEND_DIR/.venv"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is required"
  exit 1
fi
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN is required"
  exit 1
fi
if [[ -z "${TELEGRAM_CHAT_ID:-}" ]]; then
  echo "ERROR: TELEGRAM_CHAT_ID is required"
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl git nginx certbot python3-certbot-nginx python3.12 python3.12-venv python3-pip build-essential

# Install Node 20.x
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi

mkdir -p "$APP_ROOT"

# Expect repo already copied/cloned to /opt/nepse. If script is run from repo root, sync it.
if [[ -d "$(pwd)/nepse_ai_trading" && -d "$(pwd)/nepse-saas-frontend" ]]; then
  rsync -a --delete "$(pwd)/" "$APP_ROOT/"
fi

# Backend setup
python3.12 -m venv "$BACKEND_VENV"
"$BACKEND_VENV/bin/pip" install --upgrade pip
"$BACKEND_VENV/bin/pip" install -r "$BACKEND_DIR/requirements.txt"

mkdir -p /var/lib/nepse
mkdir -p /var/log/nepse
chown -R root:root /var/lib/nepse /var/log/nepse

cat >/etc/nepse-backend.env <<EOF
DATABASE_URL=sqlite:////var/lib/nepse/nepse.db
OPENAI_API_KEY=${OPENAI_API_KEY}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
SHAREHUB_AUTH_TOKEN=${SHAREHUB_AUTH_TOKEN:-}
SHAREHUB_AUTH_COOKIES=${SHAREHUB_AUTH_COOKIES:-}
LOG_LEVEL=INFO
EOF
chmod 600 /etc/nepse-backend.env

# Frontend setup
cd "$FRONTEND_DIR"
npm install
NEXT_PUBLIC_API_URL="https://${DOMAIN_API}" npm run build

cat >/etc/nepse-frontend.env <<EOF
NODE_ENV=production
PORT=3000
NEXT_PUBLIC_API_URL=https://${DOMAIN_API}
EOF
chmod 600 /etc/nepse-frontend.env

# Install systemd services
cp "$APP_ROOT/deploy/vm/nepse-backend.service" /etc/systemd/system/nepse-backend.service
cp "$APP_ROOT/deploy/vm/nepse-frontend.service" /etc/systemd/system/nepse-frontend.service
systemctl daemon-reload
systemctl enable nepse-backend nepse-frontend
systemctl restart nepse-backend nepse-frontend

# Nginx
cp "$APP_ROOT/deploy/vm/nginx-nepse.conf" /etc/nginx/sites-available/nepse
ln -sf /etc/nginx/sites-available/nepse /etc/nginx/sites-enabled/nepse
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo "Services status:"
systemctl --no-pager --full status nepse-backend | sed -n '1,12p'
systemctl --no-pager --full status nepse-frontend | sed -n '1,12p'

echo
echo "Initial HTTP checks:"
curl -sS http://127.0.0.1:8000/health || true
curl -sS -I http://127.0.0.1:3000 | head -n 1 || true

echo
echo "Next manual step after DNS A records point to this VM:"
echo "certbot --nginx -d ${DOMAIN_FRONTEND} -d ${DOMAIN_API} --redirect --agree-tos -m your-email@example.com"
