#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  DocSync Remote Client Setup
#  Run this on remote hosts to configure them as a DocSync source.
#
#  This script:
#    • Installs DocSync (if not present)
#    • Creates a docs/ directory structure in your project
#    • Generates SSH keypair for the central DocSync to pull from this host
#    • Outputs YAML configuration for the central DocSync server
#
#  Usage:
#    curl -sSL https://your-docsync-server/scripts/setup-remote-client.sh | bash
#    # Or download and run locally:
#    bash setup-remote-client.sh /path/to/your/project
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; AMBER='\033[0;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC}  $1"; }
warn() { echo -e "${AMBER}!${NC}  $1"; }
info() { echo -e "   ${BLUE}→${NC} $1"; }
err()  { echo -e "${RED}✗${NC}  $1"; exit 1; }
hdr()  { echo -e "\n${BOLD}${AMBER}── $1 ──${NC}"; }

# ── Arguments ─────────────────────────────────────────────────────────────
PROJECT_PATH="${1:-$(pwd)}"
PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"
PROJECT_NAME="${2:-$(basename "$PROJECT_PATH")}"

# Central DocSync server (prompt if not set)
CENTRAL_DOCSYNC_HOST="${DOCSYNC_CENTRAL_HOST:-}"
CENTRAL_DOCSYNC_USER="${DOCSYNC_CENTRAL_USER:-docsync}"

# ── Header ────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}DocSync Remote Client Setup${NC}"
echo "═══════════════════════════"
echo ""
echo "This script prepares this host as a documentation source for a"
echo "central DocSync instance. It will:"
echo "  1. Check/install DocSync CLI"
echo "  2. Create docs/ structure in: $PROJECT_PATH"
echo "  3. Set up SSH access for the central DocSync"
echo "  4. Output YAML to add to your central DocSync config"
echo ""

# ── Validate project exists ───────────────────────────────────────────────
[[ -d "$PROJECT_PATH" ]] || err "Project path does not exist: $PROJECT_PATH"
ok "Project path: $PROJECT_PATH"

# ── Check/Install DocSync ─────────────────────────────────────────────────
hdr "Checking DocSync Installation"

if command -v docsync &>/dev/null; then
    ok "DocSync already installed: $(docsync --version 2>/dev/null || echo 'version unknown')"
else
    warn "DocSync not found. Installing..."

    # Check Python version
    python3 --version &>/dev/null || err "python3 not found — install Python 3.11+ first"
    PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYMAJ=$(echo "$PYVER" | cut -d. -f1)
    PYMIN=$(echo "$PYVER" | cut -d. -f2)
    [[ $PYMAJ -lt 3 || ($PYMAJ -eq 3 && $PYMIN -lt 11) ]] \
        && err "Python 3.11+ required (found $PYVER)"

    # Install via pip
    pip3 install docsync --break-system-packages -q 2>/dev/null \
        || pip3 install docsync -q \
        || err "Failed to install DocSync via pip"

    ok "DocSync installed successfully"
fi

# ── Create docs directory structure ───────────────────────────────────────
hdr "Creating Documentation Structure"

DOCS_DIR="$PROJECT_PATH/docs"
mkdir -p "$DOCS_DIR"
ok "Created docs/ directory"

# Create README.md if it doesn't exist
if [[ ! -f "$PROJECT_PATH/README.md" ]]; then
    cat > "$PROJECT_PATH/README.md" << 'EOF'
# Project Documentation

Welcome to the project documentation.

## Getting Started

Add your documentation files to the `docs/` directory.

## Structure

- `README.md` — Project overview (this file)
- `docs/*.md` — Additional documentation pages
- `docs/guide/` — Guides and tutorials
- `docs/reference/` — Reference documentation

EOF
    ok "Created README.md template"
else
    ok "README.md already exists"
fi

# Create initial docs if empty
if [[ ! -f "$DOCS_DIR/README.md" && ! -f "$DOCS_DIR/index.md" ]]; then
    cat > "$DOCS_DIR/README.md" << EOF
---
title: "${PROJECT_NAME} Documentation"
description: "Documentation for ${PROJECT_NAME}"
order: 0
---

# ${PROJECT_NAME}

Welcome to the documentation for ${PROJECT_NAME}.

## Overview

This documentation is automatically synced to the central DocSync wiki.

## Sections

- [Getting Started](./getting-started.md)
- [API Reference](./reference/)
- [Troubleshooting](./troubleshooting.md)

EOF
    ok "Created docs/README.md"
fi

# Create getting started guide
if [[ ! -f "$DOCS_DIR/getting-started.md" ]]; then
    cat > "$DOCS_DIR/getting-started.md" << 'EOF'
---
title: "Getting Started"
description: "Quick start guide"
order: 1
---

# Getting Started

## Installation

```bash
# Add installation steps here
```

## Configuration

```bash
# Add configuration steps here
```

## Usage

```bash
# Add usage examples here
```

EOF
    ok "Created docs/getting-started.md"
fi

# Create troubleshooting guide
if [[ ! -f "$DOCS_DIR/troubleshooting.md" ]]; then
    cat > "$DOCS_DIR/troubleshooting.md" << 'EOF'
---
title: "Troubleshooting"
description: "Common issues and solutions"
order: 99
---

# Troubleshooting

## Common Issues

### Issue: Example problem

**Solution:** Example solution steps.

EOF
    ok "Created docs/troubleshooting.md"
fi

mkdir -p "$DOCS_DIR/reference"
ok "Created docs/reference/ directory"

# ── SSH Key Setup ─────────────────────────────────────────────────────────
hdr "SSH Key Setup for Central DocSync"

SSH_DIR="$HOME/.ssh"
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

# Generate keypair specifically for docsync
KEY_NAME="docsync_${PROJECT_NAME,,}"  # lowercase
KEY_PATH="$SSH_DIR/$KEY_NAME"

if [[ -f "$KEY_PATH" ]]; then
    warn "SSH key already exists: $KEY_PATH"
else
    ssh-keygen -t ed25519 -C "docsync-$PROJECT_NAME-$(hostname)" -f "$KEY_PATH" -N "" &>/dev/null
    ok "Generated SSH key: $KEY_PATH"
fi

# Get public key content
PUB_KEY=$(cat "${KEY_PATH}.pub")
ok "Public key ready"

# ── Collect Central DocSync Info ─────────────────────────────────────────
hdr "Central DocSync Configuration"

if [[ -z "$CENTRAL_DOCSYNC_HOST" ]]; then
    echo ""
    read -rp "Enter your central DocSync server hostname/IP: " CENTRAL_DOCSYNC_HOST
fi

if [[ -z "$CENTRAL_DOCSYNC_HOST" ]]; then
    warn "No central server specified — skipping SSH authorization"
else
    echo ""
    info "To authorize this host, run on the central DocSync server:"
    echo ""
    echo -e "${BOLD}  # Add the public key to the docsync user:${NC}"
    echo -e "  echo '$PUB_KEY' >> ~/.ssh/authorized_keys"
    echo ""

    # Test connectivity if user wants
    read -rp "Test SSH connectivity now? [y/N]: " TEST_SSH
    if [[ "$TEST_SSH" =~ ^[Yy]$ ]]; then
        if ssh -o BatchMode=yes -o ConnectTimeout=5 -i "$KEY_PATH" "${CENTRAL_DOCSYNC_USER}@${CENTRAL_DOCSYNC_HOST}" "echo 'SSH OK'" 2>/dev/null; then
            ok "SSH connectivity verified"
        else
            warn "SSH connection failed — you may need to add the key to the server first"
            info "Run the command above on the central DocSync server, then re-run this script"
        fi
    fi
fi

# ── Generate YAML Configuration ────────────────────────────────────────────
hdr "Generated DocSync Configuration"

# Get this host's IP/hostname for the YAML
THIS_HOST=$(hostname -I 2>/dev/null | awk '{print $1}' || hostname)
THIS_USER=$(whoami)

# Create category from project name (lowercase, first word)
CATEGORY="Projects"

# Generate the YAML snippet
cat << EOF

${BOLD}=== Add this to your central DocSync config (~/.config/docsync/docsync.yaml) ===${NC}

  - name: "${PROJECT_NAME}"
    type: remote
    host: "${THIS_HOST}"
    user: "${THIS_USER}"
    key: "~/.ssh/${KEY_NAME}"
    path: "${PROJECT_PATH}"
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
      - ".pytest_cache/**"
      - "venv/**"
      - "*.egg-info/**"
    category: "${CATEGORY}"
    icon: "document"
    backup:
      enabled: true
      include_all: true
      exclude:
        - ".git/**"
        - "node_modules/**"
        - "__pycache__/**"
        - "venv/**"
      priority: "normal"

${BOLD}=== On the central DocSync server, run: ===${NC}

  docsync check    # Verify connectivity
  docsync sync     # Pull documentation

EOF

# ── Save configuration snippet ─────────────────────────────────────────────
SNIPPET_FILE="$PROJECT_PATH/.docsync-remote.yaml"
cat > "$SNIPPET_FILE" << EOF
# DocSync Remote Source Configuration
# Add this to your central DocSync server's ~/.config/docsync/docsync.yaml

  - name: "${PROJECT_NAME}"
    type: remote
    host: "${THIS_HOST}"
    user: "${THIS_USER}"
    key: "~/.ssh/${KEY_NAME}"
    path: "${PROJECT_PATH}"
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
      - ".pytest_cache/**"
      - "venv/**"
      - "*.egg-info/**"
    category: "${CATEGORY}"
    icon: "document"
    backup:
      enabled: true
      include_all: true
      exclude:
        - ".git/**"
        - "node_modules/**"
        - "__pycache__/**"
        - "venv/**"
      priority: "normal"
EOF

ok "Saved configuration snippet to: $SNIPPET_FILE"

# ── Summary ────────────────────────────────────────────────────────────────
hdr "Setup Complete!"

echo ""
echo "${BOLD}Next Steps:${NC}"
echo ""
echo "  1. ${BOLD}On this host:${NC}"
echo "     • Documentation structure created in: $PROJECT_PATH/docs/"
echo "     • SSH key saved to: $KEY_PATH"
echo "     • Config snippet saved to: $SNIPPET_FILE"
echo ""
echo "  2. ${BOLD}On the central DocSync server:${NC}"
echo "     • Add the public key to ~/.ssh/authorized_keys:"
echo "       echo '$PUB_KEY' >> ~/.ssh/authorized_keys"
echo "     • Add the YAML snippet (from $SNIPPET_FILE) to ~/.config/docsync/docsync.yaml"
echo "     • Run: docsync check && docsync sync"
echo ""
echo "  3. ${BOLD}Edit your documentation:${NC}"
echo "     • Start with: $PROJECT_PATH/README.md"
echo "     • Add pages to: $PROJECT_PATH/docs/"
echo ""

ok "Remote client setup complete!"
