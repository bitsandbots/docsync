# Agent Instructions

## Documentation

- **[docs/cli.md](docs/cli.md)** — Full CLI reference
- **[docs/opencode.md](docs/opencode.md)** — OpenCode skills and configuration

## Commands

```bash
pytest                                    # Run all tests
pytest tests/test_config.py               # Single file
pytest tests/test_config.py::TestLoadConfig::test_loads_valid_yaml  # Single test

docsync init                              # Create ~/.config/docsync/docsync.yaml
docsync check                             # Validate config + test SSH
docsync sync                              # Full sync
docsync sync --source NAME                # Single source
docsync watch --debounce 3                 # Continuous sync (requires inotify-tools)
docsync serve --port 8484                  # Dev server
docsync all                               # sync + backup in sequence
```

## Paths

- **Config:** `~/.config/docsync/docsync.yaml` (override with `--config` or `DOCSYNC_CONFIG`)
- **Template:** `docsync.yaml.example` at repo root
- **Cache:** `~/.cache/docsync/` — contains `manifest.json` (SHA-256 hashes) and `staging/SOURCE/` for remote sources

## Architecture

Pipeline: **collect → parse → generate**

- `sync.py` — orchestrates the pipeline
- `collector.py` — walks local paths or rsyncs remote sources to cache, applies include/exclude globs
- `parser.py` — YAML front matter + markdown-it-py rendering (html disabled for XSS)
- `generator.py` — Jinja2 templates, navigation tree, 11+ page types
- `manifest.py` — tracks file hashes to avoid re-parsing unchanged files

**Backup subsystem:** `docsync/backup/` — `engine.py`, `snapshot.py` (zstd/gzip archives), `retention.py`, `verify.py`, `restore.py`, `report.py`

## Notes

- Python 3.11+ required
- `docsync watch` requires `inotify-tools` (install: `sudo apt install inotify-tools`)
- Remote sources require SSH key auth; run `ssh-copy-id user@host` first
- Markdown front matter fields: `title`, `description`, `tags`, `order`