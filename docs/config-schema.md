# DocSync Configuration Schema

## Configuration File Location

Default: `~/.config/docsync/docsync.yaml`

Override: `DOCSYNC_CONFIG=/path/to/config.yaml` or `--config /path/to/config.yaml`

## Complete Schema

```yaml
site:
  title: "DocSync Wiki"           # Site title
  output_dir: "/var/www/docsync"  # Static site output directory
  base_url: "http://localhost:8484"  # Base URL for generated links

sync:
  schedule: "0 */4 * * *"         # Cron schedule for automatic sync (optional)

backup:
  enabled: true                   # Enable/disable backups
  base_dir: "/mnt/backups/docsync"  # Root backup directory
  strategy: "incremental"         # Strategy: "incremental" or "full"
  compression: "zstd"             # Compression: "zstd", "gzip", or "none"
  schedule: "0 2 * * *"           # Cron schedule for automatic backup (optional)
  retention:
    daily: 7                      # Keep N most recent daily snapshots
    weekly: 4                     # Keep N weekly snapshots
    monthly: 6                    # Keep N monthly snapshots
  max_total_size_gb: 50           # Maximum total backup size (warns at 80%)
  notifications:
    on_failure: true              # Send notifications on failure
    on_success: true              # Send notifications on success
    webhook_url: "https://..."    # Webhook URL for notifications

sources:
  - name: "source-name"           # Unique source name
    type: "local"                 # "local" or "remote"
    path: "/path/to/docs"         # Local path or remote path
    category: "Category Name"     # Category for grouping in UI
    description: "Description"    # Source description (optional)
    include:                      # Include patterns (glob with ** support)
      - "**/*.md"
      - "README.md"
    exclude:                      # Exclude patterns
      - "**/.git/**"
      - "**/node_modules/**"
      - "**/__pycache__/**"
    backup:                       # Per-source backup settings
      enabled: true               # Enable backup for this source
      priority: "normal"          # Priority: "high", "normal", or "low"
      include_all: true           # Include all files (no include patterns)
      exclude:                    # Additional excludes for this backup
        - "*.log"
        - "*.tmp"
      include_db: true            # Include DB dump (requires db config)
      db:
        type: "mysql"             # DB type: "mysql", "sqlite", or "postgresql"
        name: "database_name"     # Database name
        dump_command: "/usr/bin/mysqldump database_name"
        host: "localhost"         # DB host (remote only)
        user: "db_user"           # DB user
        password: "db_pass"       # DB password
```

## Site Section

| Key | Required | Description |
|-----|----------|-------------|
| `title` | No | Site title (default: "DocSync Wiki") |
| `output_dir` | Yes | Directory for generated HTML |
| `base_url` | Yes | Base URL for generated links |

## Sync Section

| Key | Required | Description |
|-----|----------|-------------|
| `schedule` | No | Cron expression for automatic sync |

## Backup Section

| Key | Required | Description |
|-----|----------|-------------|
| `enabled` | No | Enable/disable backup feature |
| `base_dir` | Yes (if enabled) | Root directory for backups |
| `strategy` | No | `incremental` (default) or `full` |
| `compression` | No | `zstd` (default), `gzip`, or `none` |
| `schedule` | No | Cron expression for automatic backup |
| `retention.daily` | No | Number of daily snapshots to keep |
| `retention.weekly` | No | Number of weekly snapshots to keep |
| `retention.monthly` | No | Number of monthly snapshots to keep |
| `max_total_size_gb` | No | Maximum total storage (warns at 80%) |
| `notifications.on_failure` | No | Send failure notifications |
| `notifications.on_success` | No | Send success notifications |
| `notifications.webhook_url` | No | Webhook URL for notifications |

## Source Options

### Common Options

| Key | Required | Description |
|-----|----------|-------------|
| `name` | Yes | Unique source identifier |
| `type` | Yes | `local` or `remote` |
| `path` | Yes | Local path or remote path |
| `category` | No | Category for UI grouping |
| `description` | No | Source description |
| `include` | No | Glob patterns for files to include |
| `exclude` | No | Glob patterns for files to exclude |

### Remote Source Options

| Key | Required | Description |
|-----|----------|-------------|
| `host` | Yes | Remote hostname |
| `user` | Yes | Remote username |
| `port` | No | SSH port (default: 22) |
| `key` | No | SSH private key path |
| `strict_host_checking` | No | Enforce known_hosts (default: false) |

### Backup Options (Per-Source)

| Key | Required | Description |
|-----|----------|-------------|
| `enabled` | No | Enable backup (default: true) |
| `priority` | No | `high`, `normal`, or `low` |
| `include_all` | No | Include all files, no include patterns |
| `exclude` | No | Additional excludes for this backup |
| `include_db` | No | Include database dump |
| `db` | No | Database configuration (if include_db: true) |

## Glob Pattern Syntax

| Pattern | Description |
|---------|-------------|
| `*` | Matches any characters except `/` |
| `?` | Matches one character except `/` |
| `**/` | Matches zero or more path components |
| `**` | Matches anything to end (including `/`) |
| Bare filename | Matches anywhere in tree |

**Examples:**
- `**/*.md` - All markdown files in any directory
- `docs/**` - Everything in docs directory
- `README.md` - Any file named README.md anywhere
- `**/config.{json,yaml}` - config.json or config.yaml anywhere

## Cron Expression Format

5-field cron format: `minute hour day month day_of_week`

| Field | Allowed Values |
|-------|----------------|
| minute | 0-59, `*`, `*/N` |
| hour | 0-23, `*`, `*/N` |
| day | 1-31, `*`, `*/N` |
| month | 1-12, `*`, `*/N` |
| day_of_week | 0-7 (0=Sunday), `*`, `*/N` |

**Examples:**
- `0 */4 * * *` - Every 4 hours
- `0 2 * * *` - Daily at 02:00
- `0 9 * * 1-5` - Weekdays at 09:00
- `*/15 * * * *` - Every 15 minutes

## Example Configurations

### Minimal Config

```yaml
site:
  output_dir: "/var/www/docsync"
  base_url: "http://localhost:8484"

sources:
  - name: "My Project"
    type: "local"
    path: "/home/user/project/docs"
```

### Full Config with All Features

```yaml
site:
  title: "Company Documentation"
  output_dir: "/var/www/docsync"
  base_url: "http://docs.company.com"

sync:
  schedule: "0 */4 * * *"

backup:
  enabled: true
  base_dir: "/mnt/backups/docsync"
  strategy: "incremental"
  compression: "zstd"
  schedule: "0 2 * * *"
  retention:
    daily: 7
    weekly: 4
    monthly: 6
  max_total_size_gb: 100
  notifications:
    on_failure: true
    webhook_url: "https://hooks.slack.com/services/..."

sources:
  - name: "API Docs"
    type: "local"
    path: "/home/user/api-docs"
    category: "Development"
    include:
      - "**/*.md"
    backup:
      enabled: true
      priority: high
      include_all: true

  - name: "Remote Project"
    type: "remote"
    host: "nexus.local"
    user: "deploy"
    port: 22
    path: "/home/deploy/project/docs"
    category: "Production"
    include:
      - "**/*.md"
    backup:
      enabled: true
      priority: normal
      include_db: true
      db:
        type: "mysql"
        name: "project_db"
        dump_command: "mysqldump project_db"

  - name: "Internal Wiki"
    type: "local"
    path: "/home/user/wiki"
    category: "Documentation"
    backup:
      enabled: true
      priority: low
      exclude:
        - "*.log"
        - "*.tmp"
        - "drafts/**"
```
