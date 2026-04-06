#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  DocSync — Install Script
#  Installs the Python package, creates directories, writes systemd units,
#  and optionally configures Apache to serve the generated site.
#
#  Usage:
#    sudo bash install.sh              # full install
#    sudo bash install.sh --no-apache  # skip Apache vhost setup
#    sudo bash install.sh --uninstall  # remove services + files
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; AMBER='\033[0;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC}  $1"; }
warn() { echo -e "${AMBER}!${NC}  $1"; }
err()  { echo -e "${RED}✗${NC}  $1"; exit 1; }
hdr()  { echo -e "\n${BOLD}${AMBER}── $1 ──${NC}"; }
info() { echo -e "   $1"; }

# ── Root check ────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && err "Run with sudo: sudo bash install.sh"

# ── Resolve paths ─────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_USER="${SUDO_USER:-coreconduit}"
DEFAULT_HOME=$(eval echo "~$DEFAULT_USER")
INSTALL_USER="$DEFAULT_USER"

SETUP_APACHE=true
UNINSTALL=false

for arg in "$@"; do
  case "$arg" in
    --no-apache)  SETUP_APACHE=false ;;
    --uninstall)  UNINSTALL=true ;;
  esac
done

# ── Paths ─────────────────────────────────────────────────────────────────
CONFIG_DIR="$DEFAULT_HOME/.config/docsync"
CACHE_DIR="$DEFAULT_HOME/.cache/docsync"
LOG_DIR="/var/log/docsync"
SITE_OUTPUT="/var/www/docsync"
SERVICE_DIR="/etc/systemd/system"

SERVICES=(docsync-sync.service docsync-backup.service docsync-web.service)
TIMERS=(docsync-sync.timer docsync-backup.timer)

# ─────────────────────────────────────────────────────────────────────────
# UNINSTALL
# ─────────────────────────────────────────────────────────────────────────
if $UNINSTALL; then
  echo -e "\n${BOLD}DocSync — Uninstall${NC}"
  echo "─────────────────────"

  hdr "Stopping and disabling services"
  for unit in "${TIMERS[@]}" "${SERVICES[@]}"; do
    systemctl stop "$unit"    2>/dev/null && ok "stopped $unit" || true
    systemctl disable "$unit" 2>/dev/null && ok "disabled $unit" || true
    rm -f "$SERVICE_DIR/$unit" && ok "removed $unit" || true
  done
  systemctl daemon-reload

  hdr "Removing log directory"
  rm -rf "$LOG_DIR" && ok "removed $LOG_DIR"

  hdr "Uninstalling Python package"
  sudo -u "$INSTALL_USER" pip3 uninstall -y docsync 2>/dev/null \
    && ok "docsync uninstalled" || warn "docsync was not installed via pip"

  echo ""
  ok "Uninstall complete. Config ($CONFIG_DIR) and site ($SITE_OUTPUT) preserved."
  exit 0
fi

# ─────────────────────────────────────────────────────────────────────────
# INSTALL
# ─────────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}DocSync — Install${NC}"
echo "──────────────────"

# ── Verify source directory ───────────────────────────────────────────────
[[ -f "$SCRIPT_DIR/pyproject.toml" ]] || err "pyproject.toml not found in $SCRIPT_DIR — run from the docsync repo root"

# ── Check dependencies ────────────────────────────────────────────────────
hdr "Checking system dependencies"

python3 --version &>/dev/null || err "python3 not found"
PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYMAJ=$(echo "$PYVER" | cut -d. -f1)
PYMIN=$(echo "$PYVER" | cut -d. -f2)
[[ $PYMAJ -lt 3 || ($PYMAJ -eq 3 && $PYMIN -lt 11) ]] \
  && err "Python 3.11+ required (found $PYVER)"
ok "Python $PYVER"

rsync --version &>/dev/null || err "rsync not found — install with: sudo apt install rsync"
ok "rsync $(rsync --version | head -1 | awk '{print $3}')"

pip3 --version &>/dev/null || err "pip3 not found — install with: sudo apt install python3-pip"
ok "pip3 found"

# ── Install Python package ────────────────────────────────────────────────
hdr "Installing Python package"
sudo -u "$INSTALL_USER" pip3 install "$SCRIPT_DIR" --break-system-packages -q \
  && ok "docsync installed (from $SCRIPT_DIR)"

# Verify the CLI is on PATH
DOCSYNC_BIN=$(sudo -u "$INSTALL_USER" which docsync 2>/dev/null || true)
[[ -z "$DOCSYNC_BIN" ]] && DOCSYNC_BIN="$DEFAULT_HOME/.local/bin/docsync"
[[ -x "$DOCSYNC_BIN" ]] || err "docsync binary not found after install — check \$PATH"
ok "binary: $DOCSYNC_BIN"

# ── Create directories ────────────────────────────────────────────────────
hdr "Creating directories"

install -d -m 755 "$LOG_DIR"
chown "$INSTALL_USER:$INSTALL_USER" "$LOG_DIR"
ok "$LOG_DIR"

install -d -m 755 "$SITE_OUTPUT"
chown "$INSTALL_USER:$INSTALL_USER" "$SITE_OUTPUT"
ok "$SITE_OUTPUT  (site output)"

sudo -u "$INSTALL_USER" mkdir -p "$CONFIG_DIR" "$CACHE_DIR/staging"
ok "$CONFIG_DIR  (config)"
ok "$CACHE_DIR   (manifest + staging cache)"

# ── Copy example config if not present ───────────────────────────────────
hdr "Configuration"
CONFIG_FILE="$CONFIG_DIR/docsync.yaml"
if [[ -f "$CONFIG_FILE" ]]; then
  warn "Config already exists — not overwriting: $CONFIG_FILE"
else
  sudo -u "$INSTALL_USER" cp "$SCRIPT_DIR/docsync.yaml.example" "$CONFIG_FILE"
  # Update output_dir to match our install location
  sed -i "s|output_dir:.*|output_dir: \"$SITE_OUTPUT\"|" "$CONFIG_FILE"
  ok "Config written: $CONFIG_FILE"
  warn "Edit the config before running docsync: nano $CONFIG_FILE"
fi

# ── Install systemd units ─────────────────────────────────────────────────
hdr "Installing systemd units"

# Write units inline so they reflect actual install paths
cat > "$SERVICE_DIR/docsync-sync.service" <<EOF
[Unit]
Description=DocSync — Sync documentation and generate site
After=network.target
Documentation=https://github.com/coreconduit/docsync

[Service]
Type=oneshot
User=$INSTALL_USER
Group=$INSTALL_USER
ExecStart=$DOCSYNC_BIN sync
StandardOutput=append:$LOG_DIR/sync.log
StandardError=append:$LOG_DIR/sync.log
TimeoutStartSec=300
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=6
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$CACHE_DIR $LOG_DIR $SITE_OUTPUT $CONFIG_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
ok "docsync-sync.service"

cat > "$SERVICE_DIR/docsync-sync.timer" <<EOF
[Unit]
Description=DocSync — Run sync every 4 hours
Requires=docsync-sync.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=4h
AccuracySec=1min
Persistent=true
Unit=docsync-sync.service

[Install]
WantedBy=timers.target
EOF
ok "docsync-sync.timer"

cat > "$SERVICE_DIR/docsync-backup.service" <<EOF
[Unit]
Description=DocSync — Run backup for all configured sources
After=network.target
Documentation=https://github.com/coreconduit/docsync

[Service]
Type=oneshot
User=$INSTALL_USER
Group=$INSTALL_USER
ExecStart=$DOCSYNC_BIN backup run
StandardOutput=append:$LOG_DIR/backup.log
StandardError=append:$LOG_DIR/backup.log
TimeoutStartSec=3600
Nice=15
IOSchedulingClass=best-effort
IOSchedulingPriority=7
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$CACHE_DIR $LOG_DIR $CONFIG_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
ok "docsync-backup.service"

cat > "$SERVICE_DIR/docsync-backup.timer" <<EOF
[Unit]
Description=DocSync — Run backup nightly at 02:00
Requires=docsync-backup.service

[Timer]
OnCalendar=*-*-* 02:00:00
RandomizedDelaySec=5min
Persistent=true
Unit=docsync-backup.service

[Install]
WantedBy=timers.target
EOF
ok "docsync-backup.timer"

cat > "$SERVICE_DIR/docsync-web.service" <<EOF
[Unit]
Description=DocSync — Local reference wiki web server
After=network.target
Documentation=https://github.com/coreconduit/docsync

[Service]
Type=simple
User=$INSTALL_USER
Group=$INSTALL_USER
ExecStart=$DOCSYNC_BIN serve --port 8484
StandardOutput=journal
StandardError=journal
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$CACHE_DIR $LOG_DIR $SITE_OUTPUT $CONFIG_DIR
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
ok "docsync-web.service"

# ── Reload and enable ─────────────────────────────────────────────────────
hdr "Enabling services"
systemctl daemon-reload
ok "daemon reloaded"

systemctl enable --now docsync-sync.timer
ok "docsync-sync.timer  (every 4 hours)"

systemctl enable --now docsync-backup.timer
ok "docsync-backup.timer  (nightly 02:00)"

systemctl enable docsync-web.service
ok "docsync-web.service  (enabled, not started yet)"

# ── Optional Apache vhost ─────────────────────────────────────────────────
if $SETUP_APACHE; then
  hdr "Apache vhost (optional)"
  if command -v apache2 &>/dev/null; then
    VHOST="/etc/apache2/sites-available/docsync.conf"
    cat > "$VHOST" <<APACHEEOF
<VirtualHost *:80>
    ServerName docsync.local
    DocumentRoot $SITE_OUTPUT

    <Directory $SITE_OUTPUT>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted

        # Clean URLs — strip .html extension
        RewriteEngine On
        RewriteCond %{REQUEST_FILENAME} !-d
        RewriteCond %{REQUEST_FILENAME} !-f
        RewriteRule ^(.+)$ \$1.html [L]
    </Directory>

    # Security headers
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"

    # Cache static assets
    <FilesMatch "\.(css|js|woff2?|png|svg|ico)$">
        Header set Cache-Control "public, max-age=604800"
    </FilesMatch>
    # No cache for HTML (content changes on sync)
    <FilesMatch "\.html$">
        Header set Cache-Control "no-cache"
    </FilesMatch>

    ErrorLog \${APACHE_LOG_DIR}/docsync_error.log
    CustomLog \${APACHE_LOG_DIR}/docsync_access.log combined
</VirtualHost>
APACHEEOF
    a2enmod rewrite headers &>/dev/null
    a2ensite docsync &>/dev/null
    systemctl reload apache2 2>/dev/null && ok "Apache vhost enabled → http://docsync.local" \
      || warn "Apache reload failed — run: sudo systemctl reload apache2"
  else
    warn "Apache not found — skipping vhost (re-run with --no-apache to suppress this)"
    info "Access the site via the built-in server: docsync serve"
  fi
fi

# ── Log rotation ──────────────────────────────────────────────────────────
hdr "Log rotation"
cat > /etc/logrotate.d/docsync <<LREOF
$LOG_DIR/*.log {
    weekly
    rotate 8
    compress
    delaycompress
    missingok
    notifempty
    create 0640 $INSTALL_USER $INSTALL_USER
}
LREOF
ok "/etc/logrotate.d/docsync"

# ── Done ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}DocSync installed successfully.${NC}"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo -e "  1. Edit config:       nano $CONFIG_FILE"
echo -e "  2. Validate:          docsync check"
echo -e "  3. First sync:        docsync sync"
echo -e "  4. Start web server:  sudo systemctl start docsync-web"
echo -e "  5. Browse:            http://localhost:8484"
echo ""
echo -e "  ${BOLD}Service status:${NC}"
echo -e "  systemctl status docsync-sync.timer docsync-backup.timer docsync-web"
echo -e ""
echo -e "  ${BOLD}Logs:${NC}"
echo -e "  tail -f $LOG_DIR/sync.log"
echo -e "  tail -f $LOG_DIR/backup.log"
echo ""
echo -e "  ${BOLD}Remote sources (SSH):${NC}"
echo -e "  ssh-copy-id user@remote-host   # authorize key on each remote host"
echo -e "  docsync check                   # verify SSH connectivity"
echo ""
