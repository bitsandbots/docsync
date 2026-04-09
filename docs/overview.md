# DocSync Overview

DocSync is a documentation wiki and backup tool designed for self-hosted, offline-capable project documentation. It collects markdown files from local directories and remote servers (via SSH/rsync), parses them, generates a static HTML site with search and navigation, and manages compressed, incremental backups with retention policies.

## Purpose and Goals

DocSync addresses several key needs:

1. **Documentation Aggregation** - Centralize markdown documentation from multiple project directories into a single searchable wiki
2. **Self-Hosted and Offline-Capable** - Runs entirely on local infrastructure with no cloud dependencies
3. **Incremental Backups** - Space-efficient backups using rsync's link-dest feature (hardlinks for unchanged files)
4. **Developer-Friendly** - Minimal configuration, automatic change detection, and fast rebuilds

## Key Features

- **Multi-source collection**: Local directories and remote servers via SSH
- **Change-aware processing**: Only re-parses files that have changed since last sync
- **Incremental backups**: Zstandard/gzip compression with hardlink-based incrementals
- **Smart retention**: Daily/weekly/monthly snapshot pruning
- **Static site generation**: Searchable HTML with Lunr.js, dark mode, responsive design
- **Admin web UI**: Flask-powered control panel and config editor
- **Systemd integration**: Automatic sync and backup timers

## Architecture Highlights

```
┌─────────────────────────────────────────────────────────────────────┐
│                              CLI Layer                              │
│                         (docsync/cli.py)                            │
└─────────────────────────────────────────────────────────────────────┘
                                     │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌──────────────┐         ┌─────────────────┐         ┌────────────────┐
│   Collect    │         │    Parse        │         │    Generate    │
│  (collector) │ ─────▶  │  (parser.py)    │ ─────▶  │  (generator)   │
│  rsync/SSH   │         │  markdown-it    │         │   Jinja2       │
└──────────────┘         └─────────────────┘         └────────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌─────────────────┐      ┌─────────────────┐         ┌────────────────┐
│   Manifest      │      │    YAML         │         │  Static Site   │
│   (manifest)    │      │  Front Matter   │         │  (HTML/JSON)   │
└─────────────────┘      │   TOC Parsing   │         └────────────────┘
                         └─────────────────┘
                                      │
                                      ▼
                          ┌───────────────────────┐
                          │    Backup Subsystem   │
                          │  (docsync/backup/)    │
                          │  snapshot/retention   │
                          └───────────────────────┘
```

## Data Pipeline

The core documentation pipeline runs in three stages:

1. **Collect**: Walks source directories (or rsyncs from remote), applies include/exclude glob patterns, tracks file SHA-256 hashes in the manifest
2. **Parse**: Extracts YAML front matter, converts markdown to HTML via `markdown-it-py`, builds table of contents from headings
3. **Generate**: Renders Jinja2 templates into a complete static site with navigation, search index, and backup status dashboard

## Usage Workflow

```bash
# Initialize with default config
docsync init

# Edit config to add your project sources
nano ~/.config/docsync/docsync.yaml

# Validate configuration
docsync check

# Collect docs, parse, generate site
docsync sync

# Start web server to browse
docsync serve --port 8484

# Run backup for all sources
docsync backup run

# List snapshots for a source
docsync backup list SOURCE_NAME
```

## Installation

Install via pip (Python 3.11+ required):

```bash
sudo pip3 install /home/coreconduit/docsync --break-system-packages
```

Or clone and install from source:

```bash
git clone https://github.com/coreconduit/docsync.git
cd docsync
sudo bash install.sh
```

## Configuration

Config location: `~/.config/docsync/docsync.yaml`

Key sections:
- `site`: Output directory, base URL, site title
- `sync`: Schedule (cron) and source definitions
- `backup`: Base directory, strategy (incremental/full), retention policy

## Project Structure

```
docsync/
├── __init__.py           # Package metadata
├── cli.py                # Click-based CLI entry point
├── config.py             # YAML config loader and validator
├── sync.py               # Pipeline orchestration
├── collector.py          # Source collection (local + rsync)
├── parser.py             # Markdown parsing with front matter
├── generator.py          # Jinja2 static site generator
├── manifest.py           # SHA-256 hash tracking
├── search.py             # Lunr.js index builder
├── utils.py              # Shared helpers
├── backup/               # Backup subsystem
│   ├── __init__.py
│   ├── snapshot.py       # Zstd/gzip snapshots
│   ├── retention.py      # Daily/weekly/monthly pruning
│   ├── engine.py         # Backup orchestration
│   ├── verify.py         # Integrity checks
│   ├── restore.py        # Snapshot/file restoration
│   ├── report.py         # Status and storage reporting
│   └── hooks.py          # DB dump pre-hooks
├── web.py                # Flask admin panel
├── templates/            # Jinja2 templates
└── static/               # CSS, JS assets
```

## License

MIT
