# Setup and Usage

## Installation

### Quick Install

```bash
git clone https://github.com/coreconduit/docsync.git
cd docsync
sudo bash install.sh
```

The install script:
1. Installs the Python package (`pip install -e .`)
2. Creates systemd services (sync timer, backup timer, web server)
3. Creates directories (`/var/log/docsync`, `/var/www/docsync`, `~/.config/docsync`, `~/.cache/docsync`)
4. Copies example config if not present
5. Optionally configures Apache vhost (http://docsync.local)

### Skip Apache Setup

```bash
sudo bash install.sh --no-apache
```

### Uninstall

```bash
sudo bash install.sh --uninstall
```

Removes systemd services and log directory. Preserves config and site output.

## Post-Installation Setup

### 1. Initialize Configuration

```bash
docsync init
```

This creates `~/.config/docsync/docsync.yaml` with a basic configuration.

### 2. Edit Configuration

```bash
nano ~/.config/docsync/docsync.yaml
```

Configure your sources:

```yaml
site:
  output_dir: "/var/www/docsync"
  base_url: "http://localhost:8484"
  title: "My Documentation"

sources:
  - name: "My Project"
    type: "local"
    path: "/home/user/my-project/docs"
    include:
      - "**/*.md"
    exclude:
      - "**/node_modules/**"
      - "**/.git/**"
    category: "Projects"
    backup:
      enabled: true
      priority: normal
```

### 3. Validate Configuration

```bash
docsync check
```

This validates YAML syntax and checks local paths exist.

### 4. Run Initial Sync

```bash
docsync sync
```

This collects all files, parses them, generates the site, and creates the manifest.

### 5. Start Web Server

```bash
# Start manually
docsync serve --port 8484

# Or as a service (installed by install.sh)
sudo systemctl start docsync-web
```

Browse to `http://localhost:8484` or `http://docsync.local` (if Apache configured) to view your documentation site.

## Remote Source Setup

For remote sources (SSH/rsync), additional setup is required:

### 1. Generate SSH Key (if not exists)

```bash
ssh-keygen -t ed25519 -C "docsync@your-server"
```

### 2. Copy Key to Remote Host

```bash
ssh-copy-id username@remote-host
```

### 3. Configure SSH (optional but recommended)

Add to `~/.ssh/config`:

```
Host remote-host
    User username
    IdentityFile ~/.ssh/id_ed25519
    StrictHostKeyChecking accept-new
```

### 4. Test SSH Connection

```bash
docsync check
```

The check command will verify SSH connectivity to all remote sources.

## Systemd Services

The `install.sh` script creates three systemd units:

| Unit | Type | Purpose | Schedule |
|------|------|---------|----------|
| `docsync-sync.timer` | Timer | Sync docs every 4 hours | OnBootSec=5min, OnUnitActiveSec=4h |
| `docsync-backup.timer` | Timer | Run backups nightly | OnCalendar=*-*-* 02:00:00 |
| `docsync-web.service` | Service | Flask web server | Started manually |

### Service Commands

```bash
# Check status
systemctl status docsync-sync.timer
systemctl status docsync-backup.timer
systemctl status docsync-web

# Manual trigger
systemctl start docsync-sync.service    # Run sync now
systemctl start docsync-backup.service  # Run backup now

# Enable/disable timers
systemctl enable --now docsync-sync.timer
systemctl disable --now docsync-sync.timer

# View logs
tail -f /var/log/docsync/sync.log
tail -f /var/log/docsync/backup.log
journalctl -u docsync-web -f
```

### Timer Details

- **Sync timer**: Runs 5 minutes after boot, then every 4 hours. Uses `Persistent=true` so missed runs execute on next boot.
- **Backup timer**: Runs nightly at 02:00 with 5-minute randomized delay. `Persistent=true` ensures missed backups run.
- **Web service**: Not started by default. Start manually with `systemctl start docsync-web`.

### Check Service Status

```bash
systemctl status docsync-sync.timer
systemctl status docsync-backup.timer
systemctl status docsync-web
```

### Enable/Disable Timers

```bash
# Sync every 4 hours
systemctl enable --now docsync-sync.timer

# Backup nightly at 02:00
systemctl enable --now docsync-backup.timer

# Web server (manual start)
systemctl start docsync-web
```

### View Logs

```bash
# Sync logs
tail -f /var/log/docsync/sync.log

# Backup logs
tail -f /var/log/docsync/backup.log

# Web server logs
journalctl -u docsync-web -f
```

## Configuration File

### Location

Default: `~/.config/docsync/docsync.yaml`

Override with environment variable:
```bash
export DOCSYNC_CONFIG="/path/to/config.yaml"
docsync --config /path/to/config.yaml check
```

### Complete Config Example

```yaml
site:
  title: "My Documentation Wiki"
  output_dir: "/var/www/docsync"
  base_url: "http://localhost:8484"

sync:
  schedule: "0 */4 * * *"  # Every 4 hours

backup:
  enabled: true
  base_dir: "/mnt/backups/docsync"
  strategy: "incremental"  # or "full"
  compression: "zstd"      # or "gzip" or "none"
  schedule: "0 2 * * *"    # Nightly at 02:00
  retention:
    daily: 7
    weekly: 4
    monthly: 6
  max_total_size_gb: 50
  notifications:
    on_failure: true
    on_success: true
    webhook_url: "https://hooks.example.com/docsync"

sources:
  - name: "Project Docs"
    type: "local"
    path: "/home/user/projects/docs"
    category: "Projects"
    include:
      - "**/*.md"
      - "README.md"
    exclude:
      - "**/node_modules/**"
      - "**/.git/**"
      - "**/__pycache__/**"
    backup:
      enabled: true
      priority: high
      include_all: true
      exclude:
        - "*.log"
        - "*.tmp"

  - name: "Remote Project"
    type: "remote"
    host: "nexus.local"
    user: "coreconduit"
    port: 22
    path: "/home/coreconduit/remote-project/docs"
    include:
      - "**/*.md"
    backup:
      enabled: true
      priority: normal
```

## Adding Sources Interactively

```bash
docsync add [path]
```

If no path is provided, you'll be prompted interactively.

## Maintenance

### Update Configuration

```bash
docsync init  # Overwrites existing config (prompted)
# OR edit ~/.config/docsync/docsync.yaml manually
```

### Verify Site Output

```bash
ls -la /var/www/docsync/
```

### Re-run Sync Manually

```bash
docsync sync
```

### Manual Backup Run

```bash
docsync backup run
```

## Troubleshooting

### Config Validation Errors

```bash
docsync check  # Shows detailed errors
```

### Path Not Found

- Ensure paths in config exist: `ls -la /path/from/config`
- Check permissions: `ls -l /path/from/config`

### SSH Connection Issues

- Test manually: `ssh user@host`
- Check key: `ssh-add -L`
- Increase timeout in config for problematic hosts

### Permission Denied (Backup)

- Ensure backup directory exists and is writable
- Check: `ls -ld /mnt/backups/docsync`

### Web Server Not Starting

- Check if port is in use: `sudo lsof -i :8484`
- Verify site exists: `ls -la /var/www/docsync/index.html`
