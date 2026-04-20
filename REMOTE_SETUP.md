# DocSync Remote Setup Guide

This guide explains how to configure remote hosts as documentation sources for your central DocSync instance.

## Scripts Overview

The `scripts/` directory contains everything needed for remote setup:

```
scripts/
├── add-remote-source.sh          # Interactive tool (run on central server)
├── batch-import-remotes.py       # Bulk import from CSV
├── install-remote-client.sh      # One-liner installer (run on remote hosts)
├── remote-health-check.py        # Verify connectivity
├── remotes-example.csv           # CSV template for batch import
├── setup-remote-client.sh        # Full-featured setup (run on remote hosts)
├── systemd/                      # Auto-sync systemd services
│   ├── docsync-remote-sync.path
│   ├── docsync-remote-sync.service
│   └── install-remote-watcher.sh
└── README.md                     # Full documentation
```

## Quick Start

### 1. Serve Scripts from Your DocSync Server

Link the scripts directory to your web output:

```bash
sudo ln -s /path/to/docsync/scripts /var/www/docsync/scripts
```

### 2. Remote Host Setup (One-Liner)

On each remote host, run:

```bash
curl -sSL http://docsync-server/scripts/install-remote-client.sh | bash
```

This:
- Installs DocSync (if needed)
- Creates `docs/` directory structure
- Generates SSH keys
- Outputs YAML to add to central config

### 3. Add to Central Config

On the central DocSync server:

```bash
# Interactive method
bash scripts/add-remote-source.sh

# Or batch import from CSV
python scripts/batch-import-remotes.py sources.csv --validate-ssh

# Test connectivity
python scripts/remote-health-check.py
```

### 4. Sync Documentation

```bash
docsync sync --source "Remote Project Name"
# Or sync all sources:
docsync sync
```

## Administration

### Check Remote Health

```bash
# Table output
python scripts/remote-health-check.py

# JSON for monitoring
python scripts/remote-health-check.py --format json

# Include backup status
python scripts/remote-health-check.py --backup-dir /mnt/backups
```

### Batch Import from CSV

Create `sources.csv`:

```csv
name,host,user,path,category,icon,ssh_key
Web Server,192.168.1.10,pi,/var/www/web,Servers,server,~/.ssh/docsync_web
Database,192.168.1.11,pi,/opt/db,Servers,database,~/.ssh/docsync_db
```

Import:

```bash
python scripts/batch-import-remotes.py sources.csv --dry-run
python scripts/batch-import-remotes.py sources.csv --validate-ssh --generate-keys
```

### Auto-Sync on Remote Hosts

Install a file watcher that triggers when docs change:

```bash
bash scripts/systemd/install-remote-watcher.sh /path/to/project
```

This creates a systemd path unit that monitors:
- `docs/` directory
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`

## Security Best Practices

1. **Dedicated SSH keys** — Each source has its own keypair
2. **Key restrictions** — Use `command="..."` in `authorized_keys` for read-only access
3. **Network isolation** — Restrict rsync/SSH to the DocSync server IP
4. **Regular audits** — Run `remote-health-check.py` in cron

## See Also

- [Scripts README](scripts/README.md) — Detailed documentation
- [CLAUDE.md](CLAUDE.md) — Project documentation
