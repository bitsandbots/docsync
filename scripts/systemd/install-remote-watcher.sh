#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  DocSync Remote Watcher — Systemd Install
#  Installs a path-based systemd watcher to trigger sync when docs change.
#
#  Usage:
#    bash install-remote-watcher.sh /path/to/project
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_PATH="${1:-$(pwd)}"
PROJECT_PATH="$(cd "$PROJECT_PATH" 2>/dev/null && pwd)" || { echo "Invalid path: $PROJECT_PATH"; exit 1; }

# Colors
GREEN='\033[0;32m'; AMBER='\033[0;33m'; NC='\033[0m'
ok() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${AMBER}!${NC} $1"; }

echo "DocSync Remote Watcher Install"
echo "================================"
echo ""

# Check for systemd
if ! command -v systemctl &>/dev/null; then
    warn "systemctl not found. This script requires systemd."
    exit 1
fi

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

# Create user systemd directory
mkdir -p "$USER_SERVICE_DIR"
ok "Created $USER_SERVICE_DIR"

# Generate unique unit name based on project path
UNIT_NAME="docsync-watcher-$(echo "$PROJECT_PATH" | sha256sum | cut -c1-8)"

# Create the path unit
PATH_UNIT_FILE="$USER_SERVICE_DIR/${UNIT_NAME}.path"
cat > "$PATH_UNIT_FILE" << EOF
[Unit]
Description=DocSync Watcher for $(basename "$PROJECT_PATH")

[Path]
PathModified=$PROJECT_PATH/docs/
PathModified=$PROJECT_PATH/README.md
PathModified=$PROJECT_PATH/CLAUDE.md
PathModified=$PROJECT_PATH/AGENTS.md

[Install]
WantedBy=default.target
EOF

ok "Created ${UNIT_NAME}.path"

# Create the service unit
SERVICE_UNIT_FILE="$USER_SERVICE_DIR/${UNIT_NAME}.service"
cat > "$SERVICE_UNIT_FILE" << EOF
[Unit]
Description=DocSync Sync Trigger for $(basename "$PROJECT_PATH")

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo "\$(date -Iseconds) Documentation changed, ready for sync" >> "$PROJECT_PATH/.docsync-status"'
StandardOutput=journal
StandardError=journal
EOF

ok "Created ${UNIT_NAME}.service"

# Reload and enable
systemctl --user daemon-reload
ok "Reloaded systemd daemon"

systemctl --user enable "${UNIT_NAME}.path"
ok "Enabled ${UNIT_NAME}.path"

systemctl --user start "${UNIT_NAME}.path"
ok "Started watcher"

echo ""
echo "Watcher installed for: $PROJECT_PATH"
echo ""
echo "Status:"
systemctl --user status "${UNIT_NAME}.path" --no-pager -l
