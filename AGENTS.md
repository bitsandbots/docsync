# Agent Instructions

## Documentation

- **[docs/cli-reference.md](docs/cli-reference.md)** — Full CLI reference
- **[docs/setup.md](docs/setup.md)** — Installation and usage guide
- **[docs/architecture.md](docs/architecture.md)** — System design and data flow

## Commands

```bash
# Development
pytest                                    # Run all tests
pytest tests/test_config.py               # Single file
pytest tests/test_config.py::TestLoadConfig::test_loads_valid_yaml  # Single test
pip install -e .                          # Dev install (required for CLI)

# CLI
docsync init                              # Create ~/.config/docsync/docsync.yaml
docsync check                             # Validate config + test SSH
docsync check --no-ssh                    # Skip SSH tests (offline/CI)
docsync sync                              # Full sync
docsync sync --source NAME                # Single source
docsync watch --debounce 3                # Continuous sync (requires inotify-tools)
docsync serve --port 8484                 # Dev server
docsync all                               # sync + backup in sequence

# Backup
docsync backup run                        # Run backup for all sources
docsync backup run --full                 # Force full (non-incremental)
docsync backup list SOURCE                # List snapshots for source
docsync backup restore SOURCE SNAPSHOT    # Restore snapshot
docsync backup verify SOURCE              # Verify integrity
docsync backup prune                      # Apply retention policy
docsync backup status                     # Show backup health
docsync backup size                       # Show storage usage

# Systemd services (installed by install.sh)
sudo systemctl start docsync-web          # Start web server
sudo systemctl status docsync-sync.timer  # Check sync timer
sudo systemctl status docsync-backup.timer # Check backup timer
tail -f /var/log/docsync/sync.log         # View sync logs
tail -f /var/log/docsync/backup.log       # View backup logs
```

## Paths

- **Config:** `~/.config/docsync/docsync.yaml` (override with `--config` or `DOCSYNC_CONFIG`)
- **Template:** `docsync.yaml.example` at repo root
- **Cache:** `~/.cache/docsync/` — contains `manifest.json` (SHA-256 hashes) and `staging/SOURCE/` for remote sources
- **Logs:** `/var/log/docsync/` — sync.log, backup.log
- **Site output:** `/var/www/docsync/`

## Architecture

Pipeline: **collect → parse → generate**

- `sync.py` — orchestrates the pipeline
- `collector.py` — walks local paths or rsyncs remote sources to cache, applies include/exclude globs
- `parser.py` — YAML front matter + markdown-it-py rendering (html disabled for XSS)
- `generator.py` — Jinja2 templates, navigation tree, 11+ page types
- `manifest.py` — tracks file hashes to avoid re-parsing unchanged files

**Backup subsystem:** `docsync/backup/` — `engine.py`, `snapshot.py` (zstd/gzip archives), `retention.py`, `verify.py`, `restore.py`, `report.py`, `hooks.py`, `notify.py`

## Notes

- Python 3.11+ required
- `docsync watch` requires `inotify-tools` (install: `sudo apt install inotify-tools`)
- Remote sources require SSH key auth; run `ssh-copy-id user@host` first
- Markdown front matter fields: `title`, `description`, `tags`, `order`
- Install via `sudo bash install.sh` creates systemd services and Apache vhost