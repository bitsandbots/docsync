#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  DocSync Remote Client — One-Line Installer
#  Serve this from your central DocSync web server for easy client setup.
#
#  Usage on remote hosts:
#    curl -sSL http://docsync.local/scripts/install-remote-client.sh | bash
#    curl -sSL http://docsync.local/scripts/install-remote-client.sh | bash -s /path/to/project
# ════════════════════════════════════════════════════════════════════════════
set -e

# Project path from argument or current directory
PROJECT_PATH="${1:-$(pwd)}"
PROJECT_NAME="${2:-$(basename "$PROJECT_PATH")}"

# Color output
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info() { echo -e "${BLUE}→${NC} $1"; }
ok()   { echo -e "${GREEN}✓${NC} $1"; }
err()  { echo -e "${RED}✗${NC} $1"; exit 1; }

echo -e "\n${BOLD}DocSync Remote Client Setup${NC}\n"

# Resolve project path
PROJECT_PATH="$(cd "$PROJECT_PATH" 2>/dev/null && pwd)" || err "Invalid path: $PROJECT_PATH"

info "Project: $PROJECT_NAME"
info "Path: $PROJECT_PATH"

# Check Python
python3 --version >/dev/null 2>&1 || err "Python 3 not found. Install Python 3.11+"

# Install DocSync
if ! command -v docsync >/dev/null 2>&1; then
    info "Installing DocSync..."
    pip3 install docsync -q 2>/dev/null || pip3 install docsync --break-system-packages -q 2>/dev/null || {
        err "Failed to install DocSync. Try manually: pip3 install docsync"
    }
    ok "DocSync installed"
else
    ok "DocSync already installed"
fi

# Create docs structure
info "Creating documentation structure..."
mkdir -p "$PROJECT_PATH/docs" "$PROJECT_PATH/docs/reference"

# Create README if missing
if [[ ! -f "$PROJECT_PATH/README.md" ]]; then
    cat > "$PROJECT_PATH/README.md" << EOF
# $PROJECT_NAME

## Documentation

- [Project Documentation](./docs/)
- [Getting Started](./docs/getting-started.md)

EOF
fi

# Create docs/README.md if missing
if [[ ! -f "$PROJECT_PATH/docs/README.md" && ! -f "$PROJECT_PATH/docs/index.md" ]]; then
    cat > "$PROJECT_PATH/docs/README.md" << EOF
---
title: "$PROJECT_NAME Documentation"
description: "Documentation for $PROJECT_NAME"
order: 0
---

# $PROJECT_NAME

Welcome to the documentation.

EOF
fi

ok "Documentation structure created"

# Generate SSH key
SSH_DIR="$HOME/.ssh"
mkdir -p "$SSH_DIR"; chmod 700 "$SSH_DIR"

KEY_NAME="docsync_${PROJECT_NAME,,}"
KEY_PATH="$SSH_DIR/$KEY_NAME"

if [[ ! -f "$KEY_PATH" ]]; then
    info "Generating SSH key..."
    ssh-keygen -t ed25519 -C "docsync-$PROJECT_NAME" -f "$KEY_PATH" -N "" >/dev/null
    ok "SSH key generated: $KEY_NAME"
else
    ok "SSH key exists: $KEY_NAME"
fi

# Output configuration
THIS_HOST=$(hostname -I 2>/dev/null | awk '{print $1}' || hostname)
THIS_USER=$(whoami)
PUB_KEY=$(cat "${KEY_PATH}.pub")

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  DocSync Configuration — Add to your central server${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
cat << YAML
  - name: "$PROJECT_NAME"
    type: remote
    host: "$THIS_HOST"
    user: "$THIS_USER"
    key: "~/.ssh/$KEY_NAME"
    path: "$PROJECT_PATH"
    strict_host_checking: false
    include:
      - "docs/**/*.md"
      - "README.md"
      - "CLAUDE.md"
      - "AGENTS.md"
    exclude:
      - ".git/**"
      - "node_modules/**"
      - "__pycache__/**"
      - "venv/**"
    category: "Projects"
    icon: "document"
    backup:
      enabled: true
      include_all: true
      priority: "normal"
YAML

echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}  SSH Public Key — Add to ~/.ssh/authorized_keys${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "$PUB_KEY"
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
ok "Setup complete!"
