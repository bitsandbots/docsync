# DocSync CLI Reference

## Command Line Interface

DocSync uses Click for its CLI. All commands support `--help` for detailed usage.

## Root Command

```bash
docsync [OPTIONS] COMMAND [ARGS]...
```

### Global Options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to docsync.yaml (default: ~/.config/docsync/docsync.yaml) |
| `--version, -V` | Show version and exit |
| `-h, --help` | Show help message and exit |

## Commands

### `docsync init`

Generate a starter configuration file.

```bash
docsync init
```

Creates `~/.config/docsync/docsync.yaml` from the included example.

### `docsync check`

Validate configuration and test connectivity.

```bash
docsync check [--no-ssh]
```

**Options:**
- `--no-ssh` - Skip SSH connectivity tests for remote sources

**Checks performed:**
1. YAML schema validation
2. Local source path existence
3. Backup base_dir writability
4. SSH connectivity (for remote sources)

**Exit codes:**
- 0 - All checks passed
- 1 - Errors found (details displayed)

### `docsync sync`

Run a full documentation sync.

```bash
docsync sync [--source NAME] [--verbose]
```

**Options:**
- `-s, --source NAME` - Sync a single named source
- `-v, --verbose` - Show per-file details

**Output:**
```
Sources: 14 (2 skipped)
Files collected: 1201
Files changed: 223
Files parsed: 150
Pages generated: 273
Duration: 31.45s
```

### `docsync status`

Show manifest statistics and per-source file counts.

```bash
docsync status
```

**Output:**
```
Manifest status
  Manifest: /home/coreconduit/.cache/docsync/manifest.json
  Last sync: 2026-04-05 16:30:00
  Total files tracked: 1201

  project-docs: 850 file(s)
  code-snippets: 150 file(s)
  ...
```

### `docsync serve`

Start a Flask-based dev server with admin control panel.

```bash
docsync serve [--port 8484]
```

**Options:**
- `-p, --port PORT` - Port to serve on (default: 8484)

**Access:**
- Site: `http://localhost:8484`
- Admin panel: `http://localhost:8484/admin`
- Config editor: `http://localhost:8484/admin/config`

### `docsync add PATH`

Interactively add a new local source to the config.

```bash
docsync add [path]
```

If no path is provided, prompts for all source details.

### `docsync watch [--debounce SECONDS]`

Watch local source paths and re-sync on file changes.

```bash
docsync watch [--debounce 3]
```

**Requirements:**
- `inotify-tools` package installed (`apt install inotify-tools`)

**Options:**
- `--debounce SECONDS` - Wait after last change before syncing (default: 3)

### `docsync all`

Run documentation sync then backup in sequence.

```bash
docsync all
```

Combines `docsync sync` followed by `docsync backup run`.

## Backup Subcommands

### `docsync backup run`

Run backup for all (or one) enabled source(s).

```bash
docsync backup run [--source NAME] [--full]
```

**Options:**
- `-s, --source NAME` - Back up a single named source
- `--full` - Force a full (non-incremental) backup

**Output:**
```
Attempting backup for 14 sources...
  Nexus: 1250 files in 14.3s
  CoreConductor: 890 files in 12.1s
...
12/14 sources backed up
```

### `docsync backup status`

Show backup health status.

```bash
docsync backup status
```

**Output:**
```
Backup Status
  Nexus       [ok]  23 snapshots  45.2 MB
    latest: 2026-04-05 16:30  1250 files
  CoreConductor [ok]  12 snapshots  18.7 MB
    latest: 2026-04-04 02:00  890 files
```

### `docsync backup list SOURCE`

List available snapshots for a source.

```bash
docsync backup list SOURCE
```

**Output:**
```
Snapshots for 'Nexus':
  2026-04-05T16-30-00  [ok]  1250 files  45.2 MB  14.3s
  2026-04-04T02-00-00  [ok]  1248 files  44.9 MB  13.8s
  2026-04-03T02-00-00  [ok]  1245 files  44.7 MB  13.5s
```

### `docsync backup restore SOURCE SNAPSHOT`

Restore a snapshot to its original source path.

```bash
docsync backup restore SOURCE SNAPSHOT
```

**Options:**
- `--dest PATH` - Restore to a custom path
- `--file RELPATH` - Restore a single file from the snapshot

**Examples:**
```bash
# Restore entire snapshot
docsync backup restore Nexus 2026-04-05T16-30-00

# Restore to alternate location
docsync backup restore Nexus 2026-04-05T16-30-00 --dest /tmp/restored

# Restore single file
docsync backup restore Nexus 2026-04-05T16-30-00 --file docs/guide.md
```

### `docsync backup prune`

Manually run retention pruning across all sources.

```bash
docsync backup prune
```

**Output:**
```
Nexus: pruned 3 snapshot(s)
CoreConductor: pruned 1 snapshot(s)
Total pruned: 4 snapshot(s)
```

### `docsync backup verify SOURCE`

Verify integrity of the latest snapshot.

```bash
docsync backup verify SOURCE
```

**Output:**
```
Verifying 2026-04-05T16-30-00...
  Snapshot 2026-04-05T16-30-00 passed integrity check
```

### `docsync backup size`

Show total backup storage usage.

```bash
docsync backup size
```

**Output:**
```
Backup Storage
  Nexus              45.2 MB  ████████████████████░░░░
  CoreConductor      18.7 MB  ██████████░░░░░░░░░░░░░░
  Textbelt            2.1 GB  ████████████████████████
  
  Total: 42.3 GB
  Limit: 50 GB  (84.6% used)
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DOCSYNC_CONFIG` | Path to config file (overrides default) |

## Configuration File

Location: `~/.config/docsync/docsync.yaml`

Override via:
```bash
docsync --config /path/to/config.yaml check
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (validation failed, missing file, etc.) |

## Logging

All command output is logged to:
- `/var/log/docsync/sync.log` - Sync operations
- `/var/log/docsync/backup.log` - Backup operations
