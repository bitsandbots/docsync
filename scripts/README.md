# DocSync Remote Setup Scripts

These scripts simplify configuring remote hosts as documentation sources for your central DocSync instance.

## Quick Overview

| Script | Purpose | Run On |
|--------|---------|--------|
| `setup-remote-client.sh` | Full interactive setup for remote hosts | Remote hosts |
| `install-remote-client.sh` | Minimal one-liner installer | Remote hosts |
| `add-remote-source.sh` | Interactive tool to add remotes to central config | Central DocSync server |
| `batch-import-remotes.py` | Batch import from CSV | Central DocSync server |
| `remote-health-check.py` | Verify SSH/rsync connectivity | Central DocSync server |
| `systemd/install-remote-watcher.sh` | Install path watcher for auto-sync | Remote hosts |

---

## Quick One-Liner (For Remote Hosts)

```bash
curl -sSL http://docsync.local/scripts/install-remote-client.sh | bash
```

---

## Setup Remote Client (`setup-remote-client.sh`)

Run this on any remote host (workstation, server, Pi node) to prepare it as a DocSync documentation source.

### What It Does

1. **Installs DocSync** (if not present)
2. **Creates documentation structure**:
   - `docs/` directory
   - `README.md` template
   - `docs/README.md` with frontmatter
   - `docs/getting-started.md` guide
   - `docs/troubleshooting.md`
3. **Generates SSH keypair** specifically for DocSync access
4. **Outputs YAML configuration** to add to the central DocSync server

### Usage

```bash
# Download and run
curl -sSL https://your-docsync-server/scripts/setup-remote-client.sh | bash

# Or with custom project path
bash setup-remote-client.sh /path/to/your/project "Project Name"

# Or download first, then run
wget https://your-docsync-server/scripts/setup-remote-client.sh
bash setup-remote-client.sh
```

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `DOCSYNC_CENTRAL_HOST` | Central DocSync hostname/IP | Prompts interactively |
| `DOCSYNC_CENTRAL_USER` | User on central DocSync | `docsync` |

---

## Add Remote Source (`add-remote-source.sh`)

Run this on your central DocSync server to interactively add a new remote source to the configuration.

### What It Does

1. **Collects remote source details** interactively
2. **Helps select or generate SSH keys**
3. **Tests SSH connectivity**
4. **Inserts YAML configuration** into `~/.config/docsync/docsync.yaml`
5. **Validates the configuration**

### Usage

```bash
bash /path/to/docsync/scripts/add-remote-source.sh
```

### Interactive Prompts

The script will ask for:
- Source name (e.g., "Web Server", "Pi Node")
- Remote hostname or IP
- Remote username
- Remote project path (e.g., `/opt/my-project`, `/home/user/app`)
- Category for grouping (e.g., "Projects", "Servers")
- Icon name (for visual grouping)
- SSH key selection (existing or generate new)

---

## Workflow: Adding a New Remote Source

### Method A: Client-Initiated (Recommended for Developers)

1. **On the remote host**, the developer runs:
   ```bash
   curl -sSL https://docsync.local/scripts/setup-remote-client.sh | bash
   ```

2. The script outputs YAML configuration. The developer copies this and sends it to the DocSync admin.

3. **On the central DocSync server**, the admin:
   - Adds the SSH public key to `~/.ssh/authorized_keys`
   - Pastes the YAML into `~/.config/docsync/docsync.yaml`
   - Runs `docsync check` and `docsync sync`

### Method B: Admin-Initiated (Recommended for Infrastructure)

1. **On the central DocSync server**, the admin runs:
   ```bash
   bash scripts/add-remote-source.sh
   ```

2. The script collects details and generates the configuration.

3. The admin copies the displayed public key to the remote host's `~/.ssh/authorized_keys`.

4. The admin tests with `docsync check` and syncs with `docsync sync`.

---

## SSH Key Management

### Security Best Practices

1. **Use dedicated keys** — Each remote source should have its own SSH keypair
2. **Restrict key usage** — Consider adding command restrictions in `authorized_keys`:
   ```
   command="/usr/bin/rrsync /path/to/docsync/source",no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAAC3... docsync-key
   ```

3. **Store keys securely** — Private keys should be `0600` permissions:
   ```bash
   chmod 600 ~/.ssh/docsync_*
   ```

### Key Location

- **Remote host**: `~/.ssh/docsync_<projectname>`
- **Central DocSync**: `~/.ssh/` (configurable during setup)

---

## Troubleshooting

### SSH Connection Fails

```bash
# Test manually with verbose output
ssh -vvv -i ~/.ssh/docsync_keyname user@remote-host

# Common fixes:
# 1. Ensure public key is in remote:~/.ssh/authorized_keys
# 2. Check remote:/etc/ssh/sshd_config has PubkeyAuthentication yes
# 3. Verify file permissions on remote:
#    chmod 700 ~/.ssh
#    chmod 600 ~/.ssh/authorized_keys
```

### Config Validation Fails

```bash
# Check for YAML syntax errors
docsync check

# Check without SSH tests (for offline debugging)
docsync check --no-ssh
```

### Permission Denied on Sync

DocSync uses rsync over SSH. The remote user needs read access to:
- All markdown files being synced
- The `docs/` directory

---

## Manual Configuration Reference

If you prefer to configure manually, here's a minimal remote source YAML:

```yaml
sources:
  - name: "My Remote Project"
    type: remote
    host: "192.168.1.100"
    user: "pi"
    key: "~/.ssh/docsync_myproject"
    path: "/opt/myproject"
    strict_host_checking: false
    include:
      - "docs/**/*.md"
      - "README.md"
    category: "Projects"
    icon: "document"
    backup:
      enabled: true
      include_all: true
      priority: "normal"
```

---

## Batch Import (`batch-import-remotes.py`)

Import multiple remote sources from a CSV file. Ideal for infrastructure-as-code deployments.

### CSV Format

```csv
name,host,user,path,category,icon,ssh_key
Web Server,192.168.1.10,pi,/var/www/web,Servers,server,~/.ssh/docsync_web
Database Pi,192.168.1.11,pi,/opt/db,Servers,database,~/.ssh/docsync_db
```

### Usage

```bash
# Dry run to preview changes
python scripts/batch-import-remotes.py sources.csv --dry-run

# Import with SSH validation
python scripts/batch-import-remotes.py sources.csv --validate-ssh

# Skip duplicates, generate new keys
python scripts/batch-import-remotes.py sources.csv --skip-existing --generate-keys
```

### Options

| Option | Purpose |
|--------|---------|
| `--dry-run` | Preview changes without modifying config |
| `--validate-ssh` | Test SSH connectivity before adding |
| `--skip-existing` | Skip sources already in config |
| `--generate-keys` | Auto-generate SSH keys for new sources |
| `--config PATH` | Specify custom config file path |

---

## Health Check (`remote-health-check.py`)

Verify connectivity and status of all remote sources.

### Usage

```bash
# Check all remotes (table output)
python scripts/remote-health-check.py

# JSON output for monitoring systems
python scripts/remote-health-check.py --format json

# Check specific source only
python scripts/remote-health-check.py --source "Web Server"

# Include backup status
python scripts/remote-health-check.py --backup-dir /mnt/backups/docsync
```

### Output Formats

- **table** (default): Human-readable with ✓/✗ status
- **json**: Machine-parseable with full details
- **csv**: Spreadsheet-compatible format

---

## Systemd Watcher (Remote Auto-Sync)

Install a path watcher that monitors documentation files and triggers sync when they change.

### Usage

```bash
bash scripts/systemd/install-remote-watcher.sh /path/to/project
```

This creates a user systemd service that watches:
- `docs/` directory
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`

When any change, a status file is updated. The central DocSync can poll this file or use a push mechanism.

### Manual Trigger

```bash
# Trigger sync manually
echo "$(date -Iseconds)" > /path/to/project/.docsync-status
```

---

## Serving Scripts from DocSync Web UI

To make these scripts available via curl, add a symlink in your web root:

```bash
# Assuming DocSync site is at /var/www/docsync/
sudo ln -s /path/to/docsync/scripts /var/www/docsync/scripts
```

Now remote hosts can install with:

```bash
curl -sSL http://docsync.local/scripts/install-remote-client.sh | bash
```

---

## Security Considerations

### SSH Key Isolation

Each source should have a dedicated key:

```bash
~/.ssh/docsync_webserver      # Private key
~/.ssh/docsync_webserver.pub  # Public key (copy to remote)
```

### Authorized Keys Command Restriction

For read-only access, restrict the key on the remote host:

```bash
# In remote:~/.ssh/authorized_keys
command="/usr/bin/rrsync /path/to/project",no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAAC3... docsync-key
```

### Network Isolation

- Run DocSync sync on a dedicated network segment if possible
- Use firewall rules to restrict rsync/SSH to the DocSync server IP
- Consider VPN or WireGuard tunnels for remote sources across the internet

---

## See Also

- [DocSync CLI Documentation](../README.md)
- [Configuration Reference](../docsync.yaml.example)
