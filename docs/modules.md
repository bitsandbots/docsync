# DocSync Modules Reference

## Core Modules

### `docsync` - Package Root

Package metadata and entry point. Defines version, author, and license.

**Constants:**
```python
__version__ = "0.1.0"
__author__ = "CoreConduit"
__license__ = "MIT"
```

### `docsync.cli` - CLI Entry Point

The Click-based command-line interface. Exposes all docsync commands.

**Main function:**
```python
def main() -> None
```

**CLI commands:**
- `check` - Validate config and test connectivity
- `sync` - Run documentation sync
- `status` - Show manifest statistics
- `serve` - Start Flask web server
- `init` - Generate starter config
- `add` - Add new source interactively
- `watch` - Watch files for changes
- `all` - Run sync + backup
- `backup` - Backup subcommands

**Key variables:**
- `CONTEXT_SETTINGS` - Click context settings
- `_echo_ok/warn/err/section()` - Helper functions for output formatting

### `docsync.config` - Configuration Management

YAML config loader and schema validator.

**Classes:**
```python
class ConfigError(Exception):
    """Raised when config file has validation errors."""

@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def ok(self) -> bool: ...
    def add_error(self, msg: str) -> None: ...
    def add_warning(self, msg: str) -> None: ...
```

**Functions:**
```python
def load_config(path: Optional[Path] = None) -> dict:
    """Load raw config dict from docsync.yaml."""

def validate_config(config: dict) -> ValidationResult:
    """Run schema validation on loaded config."""

def load_and_validate(path: Optional[Path] = None) -> tuple[dict, ValidationResult]:
    """Load config and run schema validation."""

def check_local_paths(config: dict, result: ValidationResult) -> None:
    """Verify local source paths exist."""

def check_backup_base_dir(config: dict, result: ValidationResult) -> None:
    """Verify backup base_dir is writable."""

def check_ssh_connectivity(config: dict, result: ValidationResult) -> None:
    """Test SSH connectivity for remote sources."""
```

**Validation rules:**
- `site`: requires `output_dir`, `base_url`
- `sync.schedule`: must match cron regex
- `backup.strategy`: must be `incremental` or `full`
- `backup.compression`: must be `zstd`, `gzip`, or `none`
- `backup.retention.*`: must be non-negative integers
- `sources[].type`: must be `local` or `remote`
- `sources[].backup.priority`: must be `high`, `normal`, or `low`
- `sources[].backup.db.type`: must be `mysql`, `sqlite`, or `postgresql`

### `docsync.sync` - Pipeline Orchestration

Coordinates the collect → parse → generate pipeline.

**Main function:**
```python
def run_sync(
    config: dict,
    manifest: Manifest,
    source_name: Optional[str] = None,
) -> tuple[SyncStats, list[ParsedDoc]]:
```

**SyncStats dataclass:**
```python
@dataclass
class SyncStats:
    sources_processed: int = 0
    sources_skipped: int = 0
    files_collected: int = 0
    files_changed: int = 0
    files_parsed: int = 0
    pages_generated: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
```

### `docsync.collector` - Source Collection

Collects files from local and remote sources.

**Classes:**
```python
@dataclass
class CollectedFile:
    source_name: str
    abs_path: Path
    rel_path: str
    changed: bool

@dataclass
class CollectResult:
    source_name: str
    files: list[CollectedFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
```

**Functions:**
```python
def _glob_to_re(pattern: str) -> re.Pattern:
    """Convert glob pattern with ** to compiled regex."""

def _collect_local(source: dict, manifest: Manifest) -> CollectResult:
    """Collect from local directory."""

def _collect_remote(source: dict, manifest: Manifest) -> CollectResult:
    """Stage via rsync then collect locally."""

def collect_source(source: dict, manifest: Manifest) -> CollectResult:
    """Collect for a single source config."""

def collect_all(
    config: dict,
    manifest: Manifest,
    source_name: Optional[str] = None,
) -> list[CollectResult]:
    """Collect all sources."""
```

**SSH options:**
- `ServerAliveInterval=15` - Detect dead connections
- `ServerAliveCountMax=3` - Disconnect after 3 missed keep-alives
- `GSSAPIAuthentication=no` - Avoid reverse DNS lookups
- `UseDNS=no` - Reduce banner exchange latency

### `docsync.parser` - Markdown Parsing

Parses markdown files with YAML front matter.

**Data classes:**
```python
@dataclass
class TocEntry:
    level: int      # 1-6
    text: str       # plain-text heading
    slug: str       # URL fragment

@dataclass
class ParsedDoc:
    source_name: str
    rel_path: str
    abs_path: Path
    title: str
    description: str
    tags: list[str]
    order: int
    html_body: str
    toc: list[TocEntry]
    raw_front_matter: dict[str, Any]
```

**Functions:**
```python
def parse_file(abs_path: Path, source_name: str, rel_path: str) -> Optional[ParsedDoc]:
    """Parse a single markdown file."""

def parse_files(files: list, changed_only: bool = False) -> list[ParsedDoc]:
    """Parse multiple files."""

def extract_code_docs(source_root: Path, code_docs_config: dict) -> list[ParsedDoc]:
    """Extract doc comments from Python/PHP/C++ files."""
```

**Title derivation:**
1. Front matter `title`
2. First h1 in TOC
3. Filename stem (title-cased)

### `docsync.manifest` - File Hash Tracking

SHA-256 hash tracking with file locking.

**Main class:**
```python
class Manifest:
    def __init__(self, path: Optional[Path] = None)
    
    def get_hash(source_name: str, rel_path: str) -> Optional[str]
    def is_changed(source_name: str, rel_path: str, file_path: Path) -> bool
    def update(source_name: str, rel_path: str, file_path: Path) -> str
    def remove_source(source_name: str) -> None
    def save() -> None
```

**Storage:** `~/.cache/docsync/manifest.json`

### `docsync.generator` - Static Site Generator

Jinja2-based static site generator.

**Main function:**
```python
def generate_site(
    config: dict,
    docs: list[ParsedDoc],
    recent_docs: Optional[list] = None,
    sync_timestamp: Optional[str] = None,
) -> int:
    """Generate static site. Returns page count."""
```

**Navigation model:**
```python
@dataclass
class NavCategory:
    name: str
    sources: list[NavSource]

@dataclass
class NavSource:
    name: str
    slug: str
    category: str
    type: str  # local | remote
    path: str
    docs: list[NavDoc]

@dataclass
class NavDoc:
    title: str
    url: str
    description: str = ""
```

**Page generation:**
- `index.html` - Dashboard
- `search.html` - Search page
- `updates.html` - Recent changes
- `backups.html` - Backup dashboard
- `backups/{slug}.html` - Per-source snapshot browser
- `{cat}/{src}/index.html` - Source index
- `{cat}/{src}/{doc}.html` - Individual docs

### `docsync.search` - Search Index Builder

Lunr.js-compatible search index generation.

**Functions:**
```python
def build_index(docs: list[ParsedDoc], nav_categories: list) -> list[dict]:
    """Build search entries for Lunr.js."""

def write_index(entries: list[dict], output_dir: Path) -> None:
    """Write search-index.json to output directory."""
```

**Output:** `{output_dir}/search-index.json`

### `docsync.utils` - Shared Helpers

Utility functions used throughout the project.

**Functions:**
```python
def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file."""

def ensure_dir(path: Path, mode: int = 0o755) -> Path:
    """Create directory if it doesn't exist."""

def human_size(num_bytes: int) -> str:
    """Return human-readable file size."""

def which_or_error(binary: str) -> str:
    """Return full path to binary or raise RuntimeError."""

def resolve_path(p: str) -> Path:
    """Expand ~ and env vars, resolve to absolute path."""
```

## Backup Subsystem

### `docsync.backup.snapshot` - Snapshot Creation

Creates full or incremental snapshots.

**Functions:**
```python
def timestamp_now() -> str:
    """Get current timestamp as ISO string."""

def latest_snapshot(source_backup_dir: Path) -> Optional[Path]:
    """Get most recent snapshot directory."""

def create_snapshot(
    source: dict,
    source_backup_dir: Path,
    strategy: str = "incremental",
    extra_excludes: Optional[list[str]] = None,
) -> dict:
    """Create a new snapshot. Returns metadata dict."""
```

**Options:**
- `strategy`: `incremental` (default) or `full`
- `compression`: via zstd (auto-detected)

### `docsync.backup.engine` - Backup Orchestration

Runs backups with priority ordering and retention.

**Main function:**
```python
def run_backup(
    config: dict,
    source_name: Optional[str] = None,
    force_full: bool = False,
) -> BackupStats:
```

**BackupStats:**
```python
@dataclass
class BackupStats:
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    snapshots_pruned: int = 0
    errors: list[str] = field(default_factory=list)
```

### `docsync.backup.retention` - Retention Policy

Applies daily/weekly/monthly retention.

**Policy:**
```python
@dataclass
class RetentionPolicy:
    daily: int = 7
    weekly: int = 4
    monthly: int = 6
```

**Main function:**
```python
def apply_retention(source_backup_dir: Path, policy: RetentionPolicy) -> list[str]:
    """Prune old snapshots. Returns list of deleted snapshot names."""
```

### `docsync.backup.report` - Status Reporting

Reports backup status and storage usage.

**Functions:**
```python
def backup_status(config: dict) -> list[dict]:
    """Return status for each backup-enabled source."""

def recent_backup_events(config: dict, n: int = 20) -> list[dict]:
    """Return last N backup log events."""

def snapshot_list(source_backup_dir: Path) -> list[dict]:
    """Return metadata for all snapshots."""

def backup_status_json(config: dict, output_dir: Path) -> None:
    """Write backup-status.json to site output."""
```

### `docsync.backup.verify` - Integrity Verification

Verifies snapshot integrity via SHA-256.

**Main function:**
```python
def verify_snapshot(snapshot_dir: Path) -> tuple[bool, list[str]]:
    """Verify all files in snapshot. Returns (all_ok, errors)."""
```

### `docsync.backup.restore` - Restoration

Restores snapshots and individual files.

**Functions:**
```python
def restore_snapshot(
    source_backup_dir: Path,
    snapshot_name: str,
    dest: Optional[Path] = None,
    source: Optional[dict] = None,
) -> tuple[bool, str]:

def restore_file(
    source_backup_dir: Path,
    snapshot_name: str,
    file_rel_path: str,
    dest: Optional[Path] = None,
) -> tuple[bool, str]:
```

### `docsync.backup.hooks` - Pre-Backup Hooks

Runs database dumps before backup.

**Main function:**
```python
def run_db_dump(source: dict, snapshot_dir: Path) -> Optional[str]:
    """Execute DB dump. Returns error string or None on success."""
```

**Supported DB types:**
- MySQL
- PostgreSQL
- SQLite

### `docsync.backup.notify` - Notifications

Sends webhook and SMS notifications.

**Functions:**
```python
def send_webhook(url: str, payload: dict) -> Optional[str]:
    """POST JSON payload to webhook URL."""

def send_sms(message: str) -> Optional[str]:
    """Send SMS via TextBelt."""

def notify_failure(config: dict, source_name: str, error: str) -> None:
    """Send failure notification."""

def notify_success(config: dict, source_name: str, meta: dict) -> None:
    """Send success notification."""
```

**Environment variables:**
- `TEXTBELT_KEY` - TextBelt API key
- `TEXTBELT_PHONE` - Phone number for SMS

## Web Module

### `docsync.web` - Flask Admin Panel

Flask-based admin web interface.

**Main function:**
```python
def create_app(config: dict, output_dir: Path, config_path: Path | None = None) -> Flask:
    """Create Flask application."""
```

**API endpoints:**
- `GET /` - Static site index
- `GET /admin` - Admin panel
- `GET /admin/config` - Config editor
- `POST /api/sync` - Trigger sync
- `POST /api/backup/run` - Trigger backup
- `POST /api/backup/restore` - Trigger restore
- `GET /api/check` - Run check command
- `GET /api/status` - Get manifest stats (JSON)
- `GET /api/backup/snapshots` - Get snapshot list (JSON)
- `GET /api/config` - Get config (JSON)
- `POST /api/config/raw` - Save raw YAML config
- `POST /api/config/structured` - Save structured config
- `POST /api/reload` - Reload config from disk

**SSE streaming:**
All API commands that run subprocesses use Server-Sent Events (SSE) to stream output.

## Summary

DocSync provides a complete documentation management system with:
- **CLI-based tooling** for manual and automated operations
- **Configurable backup system** with incremental snapshots and retention
- **Flask admin panel** for web-based control and configuration
- **Static site generation** with search, dark mode, and responsive design
- **Test suite** with 91 passing tests (no external dependencies required)
