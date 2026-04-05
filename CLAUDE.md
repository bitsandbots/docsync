# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

DocSync is a documentation wiki and backup tool. It collects markdown files from local directories and remote servers (SSH/rsync), parses them, generates a static HTML site with search and navigation, and manages compressed, incremental backups with retention policies.

## Commands

```bash
# Install (creates systemd services, optionally Apache vhost)
sudo bash install.sh
sudo bash install.sh --no-apache

# Run tests
pytest
pytest tests/test_config.py        # Single file
pytest tests/test_config.py::TestConfigLoading::test_valid_config  # Single test

# CLI usage
docsync init                       # Create default config at ~/.config/docsync/docsync.yaml
docsync check                      # Validate config + test SSH connectivity
docsync sync                       # Collect → parse → generate site
docsync sync --source NAME         # Single source only
docsync watch --debounce 3         # Continuous re-sync on file changes
docsync serve --port 8484          # Dev HTTP server
docsync all                        # sync + backup run

# Backup subcommands
docsync backup run
docsync backup list SOURCE
docsync backup restore SOURCE SNAPSHOT
docsync backup verify SOURCE
docsync backup status
docsync backup size
```

**Config location:** `~/.config/docsync/docsync.yaml` (override with `--config` or `DOCSYNC_CONFIG` env var)

**Runtime cache:** `~/.cache/docsync/` — manifest JSON and rsync staging directory for remote sources

## Architecture

The documentation pipeline runs in three stages: **collect → parse → generate**.

**`sync.py`** orchestrates the pipeline, calling collector → parser → manifest update → generator. The `docsync all` command wraps this with a backup pass.

**`collector.py`** — For local sources, walks the directory tree applying include/exclude glob patterns (custom glob→regex converter supporting `**`). For remote sources, uses rsync to stage into `~/.cache/docsync/staging/SOURCE/`, then applies the same local logic.

**`manifest.py`** — Tracks per-file SHA-256 hashes in `~/.cache/docsync/manifest.json`. Only changed files are re-parsed; the generator still runs in full to update navigation and timestamps.

**`parser.py`** — Extracts YAML front matter (`title`, `description`, `tags`, `order`) and renders markdown to HTML via markdown-it-py. Builds a table of contents from headings. Also handles code documentation extraction for Python, PHP, and C++. XSS is mitigated by setting `html: False` in the markdown-it renderer.

**`generator.py`** — Jinja2 renders 11+ page types including per-doc pages, per-source indexes, a search page, an updates feed, and a backup dashboard. Navigation is built as a tree: `NavCategory → NavSource → NavDoc`. Templates live in `templates/`, static assets in `static/`.

**Backup subsystem (`docsync/backup/`):**
- `engine.py` — Orchestrates per-source backup runs; applies retention after each snapshot; logs events to `BASE_DIR/_global/backup-log.jsonl`
- `snapshot.py` — Creates full or incremental archives with zstd/gzip compression; supports optional DB dumps (MySQL, PostgreSQL, SQLite) via configurable dump commands
- `retention.py` — Prunes snapshots by daily/weekly/monthly buckets
- `verify.py` / `restore.py` / `report.py` — Integrity checks, extraction, and status dashboard

## Config Schema Notes

Sources have `type: local` or `type: remote`. Remote sources add `host`, `user`, `port`, and optionally `key`. Both types use the same `include`/`exclude` glob lists and `backup:` block.

The `backup:` block under a source can set `priority: high|normal|low`, `include_all: bool`, and optionally `db:` for database dumps.

Cron schedules in `sync.schedule` and `backup.schedule` are validated at config-load time as standard 5-field cron expressions.
