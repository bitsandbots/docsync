# DocSync Backup Subsystem

The backup subsystem provides space-efficient incremental backups of all sources.

## Overview

DocSync uses rsync's `--link-dest` feature to create hardlink-based incremental backups. This means:
- Unchanged files are linked to the previous snapshot (no disk space)
- Only modified files consume additional storage
- Each snapshot appears as a complete backup

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        Backup Engine                               │
│  run_backup() → Sorts by priority → Runs snapshot for each source │
└────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Snapshot Creation                             │
│  create_snapshot() → rsync --link-dest=PREV → Zstd compression    │
└────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
          ┌─────────────────┐             ┌──────────────────┐
          │  Retention      │             │   Status/Report  │
          │  apply_retention│             │  backup_status() │
          └─────────────────┘             └──────────────────┘
```

## Snapshot Structure

```
/mnt/backups/docsync/source-name/
├── 2026-04-05T16-30-00/      # Snapshot directory
│   ├── .docsync-snapshot.json
│   ├── docs/
│   └── ...
├── 2026-04-04T02-00-00/      # Previous snapshot
│   └── ...
├── latest -> 2026-04-05T16-30-00  # Symlink to latest
└── _global/
    └── backup-log.jsonl      # Event log
```

## Snapshot Metadata

Each snapshot contains a `.docsync-snapshot.json` file:

```json
{
  "timestamp": "2026-04-05T16-30-00",
  "source_name": "my-source",
  "status": "ok",
  "strategy": "incremental",
  "link_dest": "/mnt/backups/docsync/my-source/2026-04-04T02-00-00",
  "duration_seconds": 14.35,
  "file_count": 1250,
  "size_bytes": 47384321,
  "snapshot_dir": "/mnt/backups/docsync/my-source/2026-04-05T16-30-00"
}
```

## Backup Strategy

### Incremental (Default)

Uses `rsync --link-dest` to link unchanged files from the previous snapshot.

**Command:**
```bash
rsync -a --delete --link-dest=PREV SRC/ SNAPSHOT/
```

**Benefits:**
- Space-efficient (only changed files)
- Fast (links are instant)
- Each snapshot is complete and restorable

### Full

Creates independent snapshots without hardlinking.

**Command:**
```bash
rsync -a --delete SRC/ SNAPSHOT/
```

**Use when:**
- First backup
- After retention pruning removes all previous snapshots
- Manual full backup requested

## Retention Policy

The retention policy prunes old snapshots based on daily, weekly, and monthly buckets.

### Algorithm

1. **Daily**: Keep the N most recent snapshots
2. **Weekly**: For each distinct week, keep the newest snapshot in that week (up to N weeks)
3. **Monthly**: For each distinct month, keep the newest snapshot in that month (up to N months)

### Example

With policy: `daily: 7, weekly: 4, monthly: 6`

```
Snapshots (newest first):
  2026-04-05 → KEEP (daily)
  2026-04-04 → KEEP (daily)
  2026-04-03 → KEEP (daily)
  2026-04-02 → KEEP (daily)
  2026-04-01 → KEEP (daily)
  2026-03-31 → KEEP (weekly - week 13)
  2026-03-30 → KEEP (weekly - week 13)
  2026-03-29 → DELETE (duplicate week)
  2026-03-25 → DELETE (weekly - week 12, beyond 4)
  2026-03-01 → KEEP (monthly - March)
  2026-02-15 → DELETE (monthly - February, beyond 6)
```

## Configuration

### Global Backup Settings

```yaml
backup:
  enabled: true
  base_dir: "/mnt/backups/docsync"
  strategy: "incremental"
  compression: "zstd"
  retention:
    daily: 7
    weekly: 4
    monthly: 6
  max_total_size_gb: 50
```

### Per-Source Backup Settings

```yaml
sources:
  - name: "my-source"
    type: "local"
    path: "/path/to/docs"
    backup:
      enabled: true
      priority: "high"  # high, normal, low
      include_all: true
      exclude:
        - "*.log"
        - "*.tmp"
```

## Running Backups

### Run All Backups

```bash
docsync backup run
```

### Run Single Source

```bash
docsync backup run --source "source-name"
```

### Force Full Backup

```bash
docsync backup run --full
```

### List Snapshots

```bash
docsync backup list "source-name"
```

### View Status

```bash
docsync backup status
```

### View Storage Usage

```bash
docsync backup size
```

### Verify Integrity

```bash
docsync backup verify "source-name"
```

### Manually Prune

```bash
docsync backup prune
```

### Restore Snapshot

```bash
# Restore entire snapshot
docsync backup restore "source-name" "2026-04-05T16-30-00"

# Restore to alternate location
docsync backup restore "source-name" "2026-04-05T16-30-00" --dest /tmp/restore

# Restore single file
docsync backup restore "source-name" "2026-04-05T16-30-00" --file docs/guide.md
```

## Event Logging

All backup events are logged to:
```
{base_dir}/_global/backup-log.jsonl
```

Each line is a JSON object:
```json
{"ts": "2026-04-05T16:30:00+00:00", "source": "my-source", "status": "ok", ...}
```

## Notifications

### Webhook Notifications

Configure webhook URL in backup section:
```yaml
backup:
  notifications:
    on_failure: true
    on_success: true
    webhook_url: "https://hooks.slack.com/services/..."
```

### SMS Notifications

Configure via environment variables:
```bash
export TEXTBELT_KEY="your-textbelt-key"
export TEXTBELT_PHONE="1234567890"
```

## Pruning Old Snapshots

Snapshots are automatically pruned after each successful backup according to the retention policy. Manual pruning can be done with:

```bash
docsync backup prune
```

## Debugging

### Check Latest Log

```bash
cat /mnt/backups/docsync/_global/backup-log.jsonl | tail -n 20
```

### Verify Snapshot Integrity

```bash
docsync backup verify "source-name"
```

### Manual Snapshot Listing

```bash
# List snapshot directories
ls -la /mnt/backups/docsync/source-name/

# Show snapshot metadata
cat /mnt/backups/docsync/source-name/2026-04-05T16-30-00/.docsync-snapshot.json
```

## Performance Considerations

- **rsync timeout**: 600 seconds (configurable via `timeout` in rsync command)
- **Snapshot duration**: Typically 1-30 seconds for most sources
- **Incremental advantage**: Only changed files require rsync work; unchanged files are instant hardlinks
