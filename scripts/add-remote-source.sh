#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
#  DocSync — Add Remote Source (Central Server)
#  Run this on the central DocSync server to add a new remote documentation source.
#
#  This script interactively collects remote host details, adds them to the
#  DocSync config, and validates the connection.
#
#  Usage:
#    bash add-remote-source.sh
# ════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; AMBER='\033[0;33m'; BLUE='\033[0;34m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC}  $1"; }
warn() { echo -e "${AMBER}!${NC}  $1"; }
info() { echo -e "   ${BLUE}→${NC} $1"; }
err()  { echo -e "${RED}✗${NC}  $1"; exit 1; }
hdr()  { echo -e "\n${BOLD}${AMBER}── $1 ──${NC}"; }

# ── Config paths ──────────────────────────────────────────────────────────
CONFIG_DIR="${HOME}/.config/docsync"
CONFIG_FILE="${CONFIG_DIR}/docsync.yaml"
SSH_DIR="${HOME}/.ssh"

# ── Header ────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}DocSync — Add Remote Source${NC}"
echo "════════════════════════════"
echo ""
echo "This script adds a remote documentation source to your DocSync config."
echo "The remote host must have SSH access configured."
echo ""

# ── Verify DocSync is installed ──────────────────────────────────────────
command -v docsync &>/dev/null || err "DocSync not found. Install first: pip install docsync"
ok "DocSync found: $(docsync --version 2>/dev/null || echo 'version unknown')"

# ── Ensure config exists ─────────────────────────────────────────────────
[[ -d "$CONFIG_DIR" ]] || mkdir -p "$CONFIG_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
    warn "Config file not found. Creating from example..."
    docsync init 2>/dev/null || err "Failed to create config. Run: docsync init"
fi
ok "Config file: $CONFIG_FILE"

# ── Collect remote source details ────────────────────────────────────────
hdr "Remote Source Configuration"

echo ""
read -rp "Source name (e.g., 'Web Server', 'Pi Node'): " SOURCE_NAME
[[ -z "$SOURCE_NAME" ]] && err "Source name is required"

# Check for duplicate names
if grep -q "name: \"$SOURCE_NAME\"" "$CONFIG_FILE" 2>/dev/null; then
    err "Source name already exists in config: $SOURCE_NAME"
fi

read -rp "Remote hostname or IP: " REMOTE_HOST
[[ -z "$REMOTE_HOST" ]] && err "Remote host is required"

read -rp "Remote username ($(whoami)): " REMOTE_USER
REMOTE_USER="${REMOTE_USER:-$(whoami)}"

read -rp "Remote project path (e.g., /opt/my-project): " REMOTE_PATH
[[ -z "$REMOTE_PATH" ]] && err "Remote path is required"

read -rp "Category ($(grep -E '^  - name:' "$CONFIG_FILE" 2>/dev/null | head -1 | xargs -I{} grep -A5 'name: "{}"' "$CONFIG_FILE" | grep 'category:' | head -1 | cut -d'"' -f2 || echo 'Projects')): " CATEGORY
CATEGORY="${CATEGORY:-Projects}"

read -rp "Icon name (document): " ICON
ICON="${ICON:-document}"

# ── SSH Key Selection ─────────────────────────────────────────────────────
hdr "SSH Key Configuration"

echo ""
echo "Select an SSH key for connecting to $REMOTE_HOST:"
echo ""

# List available keys
KEY_OPTIONS=()
KEY_INDEX=1

for keyfile in "$SSH_DIR"/*.pub; do
    [[ -f "$keyfile" ]] || continue
    keyname=$(basename "$keyfile" .pub)
    KEY_OPTIONS+=("$keyname")
    echo "  $KEY_INDEX) $keyname"
    ((KEY_INDEX++))
done

echo "  $KEY_INDEX) Generate new key"
echo ""

read -rp "Select key (1-$KEY_INDEX): " KEY_SELECTION

if [[ "$KEY_SELECTION" == "$KEY_INDEX" ]]; then
    # Generate new key
    read -rp "Enter name for new key (docsync_${REMOTE_HOST}): " NEW_KEY_NAME
    NEW_KEY_NAME="${NEW_KEY_NAME:-docsync_${REMOTE_HOST}}"
    NEW_KEY_PATH="$SSH_DIR/$NEW_KEY_NAME"

    if [[ -f "$NEW_KEY_PATH" ]]; then
        warn "Key already exists: $NEW_KEY_PATH"
    else
        ssh-keygen -t ed25519 -C "docsync-$SOURCE_NAME-$(hostname)" -f "$NEW_KEY_PATH" -N ""
        ok "Generated new SSH key: $NEW_KEY_NAME"
    fi
    SSH_KEY="~/.ssh/$NEW_KEY_NAME"
    PUB_KEY_PATH="$NEW_KEY_PATH.pub"
elif [[ "$KEY_SELECTION" -ge 1 && "$KEY_SELECTION" -lt "$KEY_INDEX" ]]; then
    SELECTED_KEY="${KEY_OPTIONS[$((KEY_SELECTION-1))]}"
    SSH_KEY="~/.ssh/$SELECTED_KEY"
    PUB_KEY_PATH="$SSH_DIR/$SELECTED_KEY.pub"
    ok "Using existing key: $SELECTED_KEY"
else
    err "Invalid selection"
fi

# Show public key for copying
if [[ -f "$PUB_KEY_PATH" ]]; then
    echo ""
    info "Public key to add to ${REMOTE_USER}@${REMOTE_HOST}:"
    echo ""
    cat "$PUB_KEY_PATH"
    echo ""
fi

# ── Test SSH connectivity ───────────────────────────────────────────────────
hdr "Testing SSH Connectivity"

read -rp "Test SSH connection now? [Y/n]: " TEST_CONN
if [[ ! "$TEST_CONN" =~ ^[Nn]$ ]]; then
    info "Testing: ssh -o BatchMode=yes -o ConnectTimeout=5 ${REMOTE_USER}@${REMOTE_HOST}..."

    if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
            -i "${SSH_KEY/#\~/$HOME}" "${REMOTE_USER}@${REMOTE_HOST}" "echo 'SSH OK'" 2>/dev/null; then
        ok "SSH connection successful"
    else
        warn "SSH connection failed"
        echo ""
        echo "Common causes:"
        echo "  • The public key hasn't been added to ${REMOTE_USER}@${REMOTE_HOST}:~/.ssh/authorized_keys"
        echo "  • The remote host is not reachable"
        echo "  • SSH service is not running on the remote host"
        echo ""
        read -rp "Continue anyway? [y/N]: " CONTINUE
        [[ "$CONTINUE" =~ ^[Yy]$ ]] || exit 1
    fi
fi

# ── Build YAML snippet ────────────────────────────────────────────────────
hdr "Generating Configuration"

# Create temp file with new source
TMP_CONFIG=$(mktemp)

cat > "$TMP_CONFIG" << EOF

  - name: "${SOURCE_NAME}"
    type: remote
    host: "${REMOTE_HOST}"
    user: "${REMOTE_USER}"
    key: "${SSH_KEY}"
    path: "${REMOTE_PATH}"
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
    icon: "${ICON}"
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

# Display the snippet
echo ""
echo "Configuration to be added:"
echo "────────────────────────────"
cat "$TMP_CONFIG"
echo ""

# ── Insert into config ────────────────────────────────────────────────────
read -rp "Add this source to DocSync config? [Y/n]: " CONFIRM_ADD
if [[ "$CONFIRM_ADD" =~ ^[Nn]$ ]]; then
    rm "$TMP_CONFIG"
    err "Aborted. Config saved to temp file was: $TMP_CONFIG"
fi

# Find the sources section and insert before the closing or at the end
if grep -q "^sources:" "$CONFIG_FILE"; then
    # Find the line number of the last source entry or create sources section
    LAST_SOURCE_LINE=$(grep -n "^  - name:" "$CONFIG_FILE" | tail -1 | cut -d: -f1 || true)

    if [[ -n "$LAST_SOURCE_LINE" ]]; then
        # Find where this source entry ends (next unindented line or next source)
        TOTAL_LINES=$(wc -l < "$CONFIG_FILE")
        NEXT_SOURCE_LINE=$(grep -n "^  - name:" "$CONFIG_FILE" | awk -F: '{print $1}' | awk -v line="$LAST_SOURCE_LINE" '$1 > line {print $1; exit}')

        if [[ -n "$NEXT_SOURCE_LINE" ]]; then
            # Insert before the next source
            INSERT_LINE=$((NEXT_SOURCE_LINE - 1))
        else
            # Find the end of this source entry (look for next top-level key or end of file)
            INSERT_LINE=$TOTAL_LINES
            for ((i=LAST_SOURCE_LINE+1; i<=TOTAL_LINES; i++)); do
                LINE_CONTENT=$(sed -n "${i}p" "$CONFIG_FILE")
                # Check if line starts with a letter (new top-level key)
                if [[ "$LINE_CONTENT" =~ ^[a-z] && ! "$LINE_CONTENT" =~ ^\s ]]; then
                    INSERT_LINE=$((i-1))
                    break
                fi
            done
        fi

        # Insert the new source
        head -n "$INSERT_LINE" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
        cat "$TMP_CONFIG" >> "${CONFIG_FILE}.tmp"
        tail -n +$((INSERT_LINE + 1)) "$CONFIG_FILE" >> "${CONFIG_FILE}.tmp"
        mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    else
        # No existing sources, add after "sources:"
        SOURCES_LINE=$(grep -n "^sources:" "$CONFIG_FILE" | head -1 | cut -d: -f1)
        head -n "$SOURCES_LINE" "$CONFIG_FILE" > "${CONFIG_FILE}.tmp"
        cat "$TMP_CONFIG" >> "${CONFIG_FILE}.tmp"
        tail -n +$((SOURCES_LINE + 1)) "$CONFIG_FILE" >> "${CONFIG_FILE}.tmp"
        mv "${CONFIG_FILE}.tmp" "$CONFIG_FILE"
    fi
else
    # No sources section, append to end
    cat "$TMP_CONFIG" >> "$CONFIG_FILE"
fi

rm "$TMP_CONFIG"
ok "Configuration updated: $CONFIG_FILE"

# ── Validate config ───────────────────────────────────────────────────────
hdr "Validating Configuration"

if docsync check --no-ssh 2>&1 | grep -q "error"; then
    warn "Config validation found issues. Run: docsync check"
else
    ok "Config validation passed"
fi

# ── Summary ────────────────────────────────────────────────────────────────
hdr "Remote Source Added Successfully!"

echo ""
echo "${BOLD}Source Details:${NC}"
echo "  Name:     $SOURCE_NAME"
echo "  Host:     $REMOTE_HOST"
echo "  User:     $REMOTE_USER"
echo "  Path:     $REMOTE_PATH"
echo "  SSH Key:  $SSH_KEY"
echo ""
echo "${BOLD}Next Steps:${NC}"
echo ""
echo "  1. Ensure SSH public key is authorized on ${REMOTE_HOST}:"
echo "     ssh-copy-id -i ${SSH_KEY}.pub ${REMOTE_USER}@${REMOTE_HOST}"
echo ""
echo "  2. Test the connection:"
echo "     docsync check"
echo ""
echo "  3. Sync documentation:"
echo "     docsync sync --source \"${SOURCE_NAME}\""
echo "     # Or sync all sources:"
echo "     docsync sync"
echo ""
echo "  4. View documentation:"
echo "     docsync serve"
echo ""

ok "Setup complete!"
