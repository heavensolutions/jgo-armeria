#!/bin/bash
# ═════════════════════════════════════════════════════════
# setup_server.sh — JGO Armeria Web App (AlmaLinux + CPanel)
# ═════════════════════════════════════════════════════════
# Run this ONCE on the VPS to set up the environment.
# Usage: bash setup_server.sh
# ═════════════════════════════════════════════════════════

set -e

APP_DIR="/home/$(whoami)/jgo-armeria"
APP_USER="$(whoami)"
DOMAIN="jgo.lucasfuentes.com"

echo "═══════════════════════════════════════════════"
echo "  JGO Armeria — Server Setup"
echo "  OS: AlmaLinux 9"
echo "  Domain: $DOMAIN"
echo "  App Dir: $APP_DIR"
echo "═══════════════════════════════════════════════"

# ── 1. System dependencies ──
echo ""
echo "[1/8] Installing system dependencies..."
sudo dnf install -y python3 python3-pip python3-devel git rsync nginx 2>/dev/null || true

# ── 2. Ensure app directory ──
echo ""
echo "[2/8] Setting up app directory..."
mkdir -p "$APP_DIR"
mkdir -p "$APP_DIR/uploads" "$APP_DIR/outputs"

# ── 3. Python virtual environment ──
echo ""
echo "[3/8] Setting up Python virtual environment..."
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

# ── 4. Install Python dependencies ──
echo ""
echo "[4/8] Installing Python dependencies..."
source "$APP_DIR/venv/bin/activate"
cd "$APP_DIR"
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# ── 5. Create .env file ──
echo ""
echo "[5/8] Creating .env file..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > "$APP_DIR/.env" << 'ENVEOF'
# JGO Armeria — Environment Config
FLASK_SECRET_KEY=CHANGE_ME_TO_A_RANDOM_STRING_$(openssl rand -hex 16)
FLASK_DEBUG=false

# Auth
APP_USERNAME=admin
APP_PASSWORD=CHANGE_ME_123

# Tienda Nube API
TN_STORE_ID=6696461
TN_ACCESS_TOKEN=CHANGE_ME_TO_REAL_TOKEN
TN_USER_AGENT=JGOIntegration/1.0 (admin@jgo.lucasfuentes.com)
ENVEOF

    echo "  ⚠️  EDIT .env: nano $APP_DIR/.env"
    echo "  Set APP_PASSWORD and TN_ACCESS_TOKEN!"
else
    echo "  .env already exists, skipping"
fi

# ── 6. Create systemd service ──
echo ""
echo "[6/8] Creating systemd service..."
sudo tee /etc/systemd/system/jgo-armeria.service > /dev/null << SERVICEOF
[Unit]
Description=JGO Armeria Flask Web App
After=network.target

[Service]
Type=simple
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin:/usr/bin
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=5
StandardOutput=append:$APP_DIR/logs/access.log
StandardError=append:$APP_DIR/logs/error.log

[Install]
WantedBy=multi-user.target
SERVICEOF

# Create logs dir
mkdir -p "$APP_DIR/logs"

# ── 7. Configure reverse proxy ──
echo ""
echo "[7/8] Configuring reverse proxy..."
echo ""
echo "  ┌──────────────────────────────────────────────────────┐"
echo "  │  IMPORTANT: Configure CPanel reverse proxy manually  │"
echo "  │                                                     │"
echo "  │  Since you have CPanel, you need to:                │"
echo "  │                                                     │"
echo "  │  OPTION A: Apache as reverse proxy (CPanel native)   │"
echo "  │  1. In CPanel → "Apache Configuration" → "Include Editor" │"
echo "  │  2. Add to the virtual host for $DOMAIN:         │"
echo "  │                                                     │"
echo "  │     ProxyPreserveHost On                             │"
echo "  │     ProxyPass / http://127.0.0.1:5000/               │"
echo "  │     ProxyPassReverse / http://127.0.0.1:5000/        │"
echo "  │                                                     │"
echo "  │  OPTION B: Use Node.js Selector in CPanel            │"
echo "  │  (if CPanel has "Setup Python App")                 │"
echo "  │                                                     │"
echo "  │  See docs: https://jgo.lucasfuentes.com will be     │"
echo "  │  proxied to localhost:5000 where the app runs       │"
echo "  └──────────────────────────────────────────────────────┘"

# Alternative: Install nginx as fallback if CPanel proxy is too complex
if command -v nginx &> /dev/null; then
    echo ""
    echo "  Also creating an nginx config as fallback..."
    sudo tee /etc/nginx/conf.d/jgo-armeria.conf > /dev/null << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;

    access_log /var/log/nginx/jgo-access.log;
    error_log /var/log/nginx/jgo-error.log;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Large file uploads
        client_max_body_size 50M;
        proxy_request_buffering off;
        proxy_buffering off;
    }

    location /static/ {
        alias $APP_DIR/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINXEOF
    echo "  Nginx config created at /etc/nginx/conf.d/jgo-armeria.conf"
fi

# ── 8. Enable systemd service ──
echo ""
echo "[8/8] Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable jgo-armeria
sudo systemctl start jgo-armeria

# ── Done ──
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit .env:     nano $APP_DIR/.env"
echo "  2. Start app:     sudo systemctl start jgo-armeria"
echo "  3. Check logs:    sudo journalctl -u jgo-armeria -f"
echo "  4. Health check:  curl http://127.0.0.1:5000/api/status"
echo ""
echo "  CPanel reverse proxy config:"
echo "    ProxyPass / http://127.0.0.1:5000/"
echo "    ProxyPassReverse / http://127.0.0.1:5000/"
echo ""
echo "  Or use nginx directly on port 80."
echo "═══════════════════════════════════════════════"
