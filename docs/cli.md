# CLI Reference

## Global Options

| Option | Description |
|--------|-------------|
| `--config, -c PATH` | Path to config file (default: `~/.config/docsync/docsync.yaml`) |
| `--config` | Override via `DOCSYNC_CONFIG` environment variable |
| `-V, --version` | Show version |

## Commands

### `docsync init`

Create a starter configuration file.

```bash
docsync init
```

Creates `~/.config/docsync/docsync.yaml` from the example template. Prompts before overwriting an existing config.

---

### `docsync check`

Validate configuration and test connectivity.

```bash
docsync check [--no-ssh]
```

| Flag | Description |
|------|-------------|
| `--no-ssh` | Skip SSH connectivity tests for remote sources |

**Checks performed:**
1. Config schema validation
2. Local source paths exist
3. Backup `base_dir` is writable
4. SSH connectivity for remote sources

Exit code 1 if any errors found.

---

### `docsync sync`

Run documentation sync (collect → parse → generate).

```bash
docsync sync [--source NAME] [--verbose]
```

| Flag | Description |
|------|-------------|
| `-s, --source NAME` | Sync a single named source (default: all) |
| `-v, --verbose` | Show per-file details |

**Output includes:**
- Sources processed/skipped
- Files collected, changed, parsed
- Pages generated
- Duration

---

### `docsync watch`

Watch local source paths and re-sync on changes.

```bash
docsync watch [--debounce SECONDS]
```

| Flag | Description |
|------|-------------|
| `--debounce SECONDS` | Wait time after last change before syncing (default: 3) |

**Requires:** `inotify-tools` (`sudo apt install inotify-tools`)

**Behavior:**
- Runs initial sync on start
- Monitors `modify,create,delete,move` events recursively
- Debounces rapid changes

---

### `docsync serve`

Start a development server for the generated site.

```bash
docsync serve [--port PORT]
```

| Flag | Description |
|------|-------------|
| `-p, --port PORT` | Port to serve on (default: 8484) |

Serves from `site.output_dir` config. Includes admin panel at `/admin`.

**Ctrl+C** to stop.

---

### `docsync status`

Show last sync time, file counts, and manifest state.

```bash
docsync status
```

Shows:
- Manifest path
- Last sync timestamp
- Total files tracked
- Per-source file counts

---

### `docsync all`

Run documentation sync then backup in sequence.

```bash
docsync all
```

Equivalent to running `docsync sync` followed by `docsync backup run`.

---

### `docsync add`

Interactively add a new local source to the config.

```bash
docsync add [PATH]
```

Prompts for:
- Source name (default: directory name)
- Category (default: "General")
- Include patterns (default: `**/*.md,README.md`)
- Backup enabled (default: yes)

---

## Backup Commands

### `docsync backup run`

Run backup for all (or one) enabled source(s).

```bash
docsync backup run [--source NAME] [--full]
```

| Flag | Description |
|------|-------------|
| `-s, --source NAME` | Back up a single named source |
| `--full` | Force full (non-incremental) backup |

Backups use zstd compression by default. Incremental mode only backs up changed files.

---

### `docsync backup status`

Show backup health for all sources.

```bash
docsync backup status
```

Shows per-source:
- Latest backup status (ok/error)
- Snapshot count
- Total storage size
- Latest snapshot details

---

### `docsync backup list`

List available snapshots for a source.

```bash
docsync backup list SOURCE
```

Shows: timestamp, status, file count, size, duration for each snapshot.

---

### `docsync backup restore`

Restore a snapshot (or single file).

```bash
docsync backup restore SOURCE SNAPSHOT [--dest PATH] [--file PATH]
```

| Flag | Description |
|------|-------------|
| `--dest PATH` | Restore to custom path (default: original location) |
| `--file PATH` | Restore a single file from snapshot |

---

### `docsync backup verify`

Verify integrity of the latest snapshot.

```bash
docsync backup verify SOURCE
```

Checks archive integrity and file checksums.

---

### `docsync backup prune`

Manually run retention pruning.

```bash
docsync backup prune
```

Applies retention policy (daily/weekly/monthly counts) to all sources.

---

### `docsync backup size`

Show total backup storage usage.

```bash
docsync backup size
```

Shows:
- Per-source storage with visual bar
- Total storage used
- Percentage of configured limit

---

## Configuration Paths

| Path | Description |
|------|-------------|
| `~/.config/docsync/docsync.yaml` | Main config (override with `--config` or `DOCSYNC_CONFIG`) |
| `~/.cache/docsync/manifest.json` | SHA-256 hashes for change detection |
| `~/.cache/docsync/staging/SOURCE/` | Cached remote source files |
| `/var/www/docsync/` | Default site output (configurable) |
| `/var/log/docsync/` | Log files (via systemd) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DOCSYNC_CONFIG` | Override config path |

## Systemd Services

When installed via `install.sh`:

| Service | Description |
|---------|-------------|
| `docsync-sync.timer` | Runs sync every 4 hours |
| `docsync-backup.timer` | Runs backup nightly at 02:00 |
| `docsync-web.service` | Dev server on port 8484 |

```bash
# View status
systemctl status docsync-sync.timer docsync-backup.timer docsync-web

# View logs
tail -f /var/log/docsync/sync.log
tail -f /var/log/docsync/backup.log
```