# DocSync Architecture

This document describes DocSync's high-level design, data flow, and component interactions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              User Interface                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐ │
│  │  CLI (click)    │  │ Web Server      │  │  Systemd Timers               │ │
│  │  docsync sync   │  │ docsync serve   │  │  docsync-sync.timer           │ │
│  │  docsync backup │  │ Flask app       │  │  docsync-backup.timer         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Application Layer                                  │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────┐ │
│  │   Sync Orchestrator   │  │  Backup Engine        │  │  Config Manager   │ │
│  │   run_sync()          │  │  run_backup()         │  │  validate_config()│ │
│  └───────────────────────┘  └───────────────────────┘  └───────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                    │                              │
        ┌───────────┴───────────┐   ┌──────────────┴──────────────┐
        ▼                       ▼   ▼                             ▼
┌───────────────┐   ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐
│   Collector   │   │   Parser        │  │  Manifest       │  │  Generator       │
│   (rsync/SSH) │   │  (markdown-it)  │  │  (SHA-256)      │  │  (Jinja2)        │
└───────────────┘   └─────────────────┘  └─────────────────┘  └──────────────────┘
                    │                              │
                    ▼                              ▼
          ┌────────────────────────────────────────────────────────┐
          │                   Source Directories                   │
          │  /home/user/project1/docs/    /home/user/project2/     │
          │  remote: user@host:/path/to/docs/                     │
          └────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Collection Phase (`collector.py`)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              Collection Algorithm                              │
├────────────────────────────────────────────────────────────────────────────────┤
│  For each source:                                                              │
│    Local:                                                                      │
│      Walk directory tree → Apply glob patterns → Check manifest hash           │
│    Remote:                                                                     │
│      rsync via SSH → Stage in ~/.cache/docsync/staging/NAME/                  │
│      Apply local collection logic to staged files                              │
│                                                                                │
│  Result: CollectedFile objects with:                                           │
│    - source_name, rel_path, abs_path, changed (bool)                         │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Key algorithms:**
- `_glob_to_re()`: Converts glob patterns with `**` to compiled regex
- Custom glob engine supports bare filename matching (anywhere in tree)

### 2. Manifest Tracking (`manifest.py`)

```python
# Manifest structure: { "source/rel_path": { "hash": sha256, "synced_at": timestamp } }

Manifest:
  - get_hash(source, rel) → Optional[str]
  - is_changed(source, rel, path) → bool
  - update(source, rel, path) → str  # record new hash
  - remove_source(source) → None
```

**Features:**
- SHA-256 file hashing for content change detection
- File locking to prevent concurrent modification corruption
- Atomic writes via temp file + rename

### 3. Parsing Phase (`parser.py`)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                              Markdown Parsing                                  │
├────────────────────────────────────────────────────────────────────────────────┤
│  Input: markdown file                                                          │
│    ┌─────────────────────────────────────────────────────────────────────┐    │
│    │  ---                                                                │    │
│    │  title: My Document                                                 │    │
│    │  description: A useful guide                                        │    │
│    │  tags: [tutorial, api]                                             │    │
│    │  order: 10                                                          │    │
│    │  ---                                                                │    │
│    │  # Introduction                                                     │    │
│    │  Content here...                                                    │    │
│    └─────────────────────────────────────────────────────────────────────┘    │
│                                           │                                    │
│                    ┌──────────────────────▼──────────────────────┐             │
│                    │  _extract_front_matter()                   │             │
│                    │  - YAML metadata + body split              │             │
│                    └─────────────────────────────────────────────┘             │
│                                           │                                    │
│                    ┌──────────────────────▼──────────────────────┐             │
│                    │  MarkdownIt (commonmark, html=False)       │             │
│                    │  - Renders HTML (XSS-safe)                 │             │
│                    │  - Token stream for TOC extraction         │             │
│                    └─────────────────────────────────────────────┘             │
│                                           │                                    │
│                    ┌──────────────────────▼──────────────────────┐             │
│                    │  _build_toc()                              │             │
│                    │  - Extracts heading tokens → TocEntry      │             │
│                    └─────────────────────────────────────────────┘             │
│                                           │                                    │
│                    ┌──────────────────────▼──────────────────────┐             │
│                    │  Title derivation chain:                   │             │
│                    │  1. front matter.title                    │             │
│                    │  2. First h1 in TOC                       │             │
│                    │  3. Filename stem (title-cased)          │             │
│                    └─────────────────────────────────────────────┘             │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 4. Generation Phase (`generator.py`)

```python
# Navigation tree structure
NavCategory:
  - name: str
  - sources: list[NavSource]

NavSource:
  - name: str, slug: str, category: str
  - docs: list[NavDoc]

NavDoc:
  - title: str, url: str, description: str
```

**Output pages generated:**
- `index.html` - Dashboard with category grid
- `search.html` - Lunr.js-powered search
- `updates.html` - Recent changes feed
- `backups.html` - Backup dashboard
- `backups/{slug}.html` - Per-source snapshot browser
- `{category}/{source}/index.html` - Source landing page
- `{category}/{source}/{doc}.html` - Individual doc pages

## Component Details

### Config Validation (`config.py`)

```python
# Schema validation checks:
- site.output_dir, site.base_url required
- sync.schedule matches CRON_RE
- backup.strategy ∈ {incremental, full}
- backup.compression ∈ {zstd, gzip, none}
- backup.retention.{daily,weekly,monthly} are non-negative integers
- sources[].type ∈ {local, remote}
- sources[].backup.priority ∈ {high, normal, low}
- sources[].backup.db.type ∈ {mysql, sqlite, postgresql}
```

### SSH/RSync Optimization

```python
# SSH options for remote sources:
- BatchMode=yes (no password prompts)
- ConnectTimeout=10s (fail fast)
- ServerAliveInterval=15 (detect dead connections)
- ServerAliveCountMax=3 (3 missed = disconnect)
- GSSAPIAuthentication=no (avoid reverse DNS lookups)
- UseDNS=no (reduce banner exchange latency)
- StrictHostKeyChecking (configurable per source)
```

### Backup Strategy

```python
# Incremental snapshot using rsync --link-dest
snapshot:
  - latest_snapshot() BEFORE mkdir() to find previous
  - rsync -a --delete --link-dest=PREV SRC/ SNAPSHOT/
  - Hardlinks created for unchanged files
  - Only unique data consumes new disk space

# Retention policy
- Keep N most recent daily snapshots
- Keep 1 snapshot per week (up to N weeks)
- Keep 1 snapshot per month (up to N months)
- Delete all others
```

## State Management

### Cache Directory (`~/.cache/docsync/`)

```
~/.cache/docsync/
├── manifest.json          # File hashes + timestamps
├── staging/               # Remote source staging
│   ├── project1/
│   └── project2/
└── backup/                # Temporary backup staging (if needed)
```

### Config Directory (`~/.config/docsync/`)

```
~/.config/docsync/
└── docsync.yaml           # User configuration
```

### Log Files

```
/var/log/docsync/
├── sync.log               # Sync command output
└── backup.log             # Backup command output
```

## Error Handling

- **Dead host short-circuit**: After SSH exit-255 or timeout, remaining sources on same host are skipped
- **Graceful degradation**: Single source failures don't stop entire sync
- **Atomic writes**: Config and manifest use temp file + rename pattern
- **File locking**: Manifest uses flock for concurrent process safety
