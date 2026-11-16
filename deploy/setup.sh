#!/usr/bin/env bash
# One-shot setup for CyberGuard on a fresh Ubuntu 24.04 VM.
# Run from the repository root:  bash deploy/setup.sh
# Safe to re-run: it updates code dependencies, rebuilds and restarts.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="$(whoami)"
MODEL="${OLLAMA_MODEL:-mistral:latest}"

echo "==> CyberGuard setup in ${APP_DIR} (user ${APP_USER})"

echo "==> System packages"
sudo apt-get update -y
sudo apt-get install -y \
    python3.12 python3.12-venv python3-pip \
    git curl nginx sleuthkit build-essential

if ! command -v node >/dev/null 2>&1; then
    echo "==> Node.js 20"
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "==> Ollama"
    curl -fsSL https://ollama.com/install.sh | sh
fi

sudo systemctl enable --now ollama
echo "==> Pulling ${MODEL} (about 4.4 GB the first time)"
ollama pull "${MODEL}"

echo "==> Python environment"
cd "${APP_DIR}"
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
    cp deploy/env.example .env
    echo "==> Created .env from deploy/env.example"
fi

echo "==> Frontend build"
(cd frontend && npm ci && npm run build)

mkdir -p data/uploads

echo "==> systemd service"
sed -e "s|__APP_USER__|${APP_USER}|g" -e "s|__APP_DIR__|${APP_DIR}|g" \
    deploy/cyberguard.service | sudo tee /etc/systemd/system/cyberguard.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable cyberguard
sudo systemctl restart cyberguard

echo "==> nginx"
sed -e "s|__APP_DIR__|${APP_DIR}|g" deploy/nginx.conf \
    | sudo tee /etc/nginx/sites-available/cyberguard >/dev/null
sudo ln -sf /etc/nginx/sites-available/cyberguard /etc/nginx/sites-enabled/cyberguard
sudo rm -f /etc/nginx/sites-enabled/default
# nginx must be able to walk into the home directory to read frontend/dist.
chmod o+x "$HOME"
sudo nginx -t
sudo systemctl reload nginx

echo "==> Waiting for the API"
for _ in $(seq 1 60); do
    if curl -fsS http://127.0.0.1/api/health >/dev/null 2>&1; then
        echo "==> CyberGuard is up: http://$(curl -fsS -H 'Metadata-Flavor: Google' \
            http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || echo '<VM external IP>')/"
        exit 0
    fi
    sleep 2
done

echo "!! The API did not come up. Check: journalctl -u cyberguard -n 100"
exit 1
