# DocSync

A documentation wiki and backup tool for collecting, organizing, and versioning project documentation.

DocSync aggregates markdown files from local directories and remote servers (SSH/rsync), generates a searchable static HTML site with navigation, and manages compressed incremental backups with retention policies.

## Features

- **Multi-source aggregation** — Collect docs from local paths and remote SSH hosts
- **Static site generation** — Searchable HTML wiki with three-tier navigation
- **Incremental backups** — Zstd/gzip compressed snapshots with retention policies
- **Database dumps** — Optional MySQL, PostgreSQL, SQLite dumps in backups
- **Admin dashboard** — Flask web UI for sync, backup, and config management
- **Remote setup tools** — Scripts for configuring remote documentation sources
- **WCAG 2.2 AA compliant** — Accessible UI with CoreConduit brand theming

## Quick Start

```bash
# Install
pip install docsync

# Initialize config
docsync init

# Add a documentation source
docsync add-source /path/to/project

# Sync and generate site
docsync sync

# Start dev server
docsync serve --port 8484
```

## CLI Commands

```bash
docsync init                    # Create default config
docsync check                    # Validate config + test SSH
docsync add-source PATH          # Interactively add source
docsync sync                     # Collect → parse → generate
docsync sync --source NAME       # Single source only
docsync watch --debounce 3       # Continuous re-sync on changes
docsync serve --port 8484        # Dev HTTP server
docsync all                      # sync + backup run

# Backup commands
docsync backup run               # Run backup
docsync backup run --full        # Force full snapshot
docsync backup list SOURCE       # List snapshots
docsync backup restore SOURCE ID # Restore snapshot
docsync backup verify SOURCE     # Integrity check
docsync backup prune             # Apply retention policy
docsync backup status            # Show backup stats
```

## Configuration

Config lives at `~/.config/docsync/docsync.yaml`:

```yaml
site:
  title: "My Docs Wiki"
  output_dir: "/var/www/docsync"
  base_url: "http://localhost:8484"

sync:
  schedule: "0 */4 * * *"   # cron: every 4 hours

backup:
  enabled: true
  base_dir: "/mnt/backups/docsync"
  retention:
    daily: 7
    weekly: 4
    monthly: 6
  compression: "zstd"

sources:
  - name: "My Project"
    type: local
    path: "/home/user/projects/myproject"
    include: ["docs/**/*.md", "README.md"]
    category: "Projects"
    backup:
      enabled: true
      include: ["src/**/*.py"]
```

## Remote Sources

Configure remote hosts via SSH:

```yaml
sources:
  - name: "Remote Server"
    type: remote
    host: "server.example.com"
    user: "docs"
    path: "/var/docs"
    include: ["**/*.md"]
    strict_host_checking: false
```

Use the remote setup scripts for one-liner installation on remote hosts:

```bash
curl -sSL http://your-server:8484/scripts/install-remote-client.sh | bash
```

## Architecture

DocSync runs a three-stage pipeline: **collect → parse → generate**

1. **Collector** — Walks local dirs or rsyncs from remote hosts
2. **Parser** — Extracts YAML front matter, renders markdown to HTML
3. **Generator** — Jinja2 renders static site with navigation tree

The backup subsystem creates incremental zstd/gzip archives with optional database dumps.

## Documentation

- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [CLI Reference](docs/cli-reference.md)
- [Config Schema](docs/config-schema.md)
- [Backup Subsystem](docs/backup-subsystem.md)
- [Remote Setup Guide](REMOTE_SETUP.md)

## Installation

### From Source

```bash
git clone https://github.com/bitsandbots/docsync.git
cd docsync
pip install -e .
```

### Production (systemd + Apache)

```bash
sudo bash install.sh
```

Creates systemd services for sync/backup and optional Apache vhost.

## Requirements

- Python 3.11+
- rsync (for remote sources)

## License

MIT