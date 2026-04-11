"""YAML config loader and validator for DocSync."""

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

# ── Defaults ─────────────────────────────────────────────────────────────────

DEFAULT_CONFIG_PATH = Path("~/.config/docsync/docsync.yaml").expanduser()

VALID_BACKUP_STRATEGIES = {"incremental", "full"}
VALID_COMPRESSIONS = {"zstd", "gzip", "none"}
VALID_PRIORITIES = {"high", "normal", "low"}
VALID_DB_TYPES = {"mysql", "sqlite", "postgresql"}

CRON_RE = re.compile(
    r"^(\*(?:/\d+)?|[\d,\-\/]+)\s+"
    r"(\*(?:/\d+)?|[\d,\-\/]+)\s+"
    r"(\*(?:/\d+)?|[\d,\-\/]+)\s+"
    r"(\*(?:/\d+)?|[\d,\-\/]+)\s+"
    r"(\*(?:/\d+)?|[\d,\-\/]+)$"
)


# ── Error collection ──────────────────────────────────────────────────────────


class ConfigError(Exception):
    """Raised when the config file has validation errors."""


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)


# ── Schema helpers ────────────────────────────────────────────────────────────


def _require(d: dict, key: str, section: str, result: ValidationResult) -> Any:
    """Return d[key] or record an error if missing."""
    if key not in d:
        result.add_error(f"[{section}] missing required key: '{key}'")
        return None
    return d[key]


def _valid_cron(expr: str) -> bool:
    return bool(CRON_RE.match(expr.strip()))


def _resolve_path(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


# ── Per-section validators ────────────────────────────────────────────────────


def _validate_site(site: dict, result: ValidationResult) -> None:
    _require(site, "output_dir", "site", result)
    _require(site, "base_url", "site", result)


def _validate_sync(sync: dict, result: ValidationResult) -> None:
    if "schedule" in sync and not _valid_cron(sync["schedule"]):
        result.add_error(f"[sync] invalid cron expression: '{sync['schedule']}'")


def _validate_backup_global(backup: dict, result: ValidationResult) -> None:
    if not backup.get("enabled", True):
        return

    _require(backup, "base_dir", "backup", result)

    strategy = backup.get("strategy", "incremental")
    if strategy not in VALID_BACKUP_STRATEGIES:
        result.add_error(
            f"[backup] invalid strategy '{strategy}'; "
            f"must be one of: {', '.join(VALID_BACKUP_STRATEGIES)}"
        )

    compression = backup.get("compression", "zstd")
    if compression not in VALID_COMPRESSIONS:
        result.add_error(
            f"[backup] invalid compression '{compression}'; "
            f"must be one of: {', '.join(VALID_COMPRESSIONS)}"
        )

    if "schedule" in backup and not _valid_cron(backup["schedule"]):
        result.add_error(f"[backup] invalid cron expression: '{backup['schedule']}'")

    retention = backup.get("retention", {})
    for key in ("daily", "weekly", "monthly"):
        val = retention.get(key)
        if val is not None and (not isinstance(val, int) or val < 0):
            result.add_error(f"[backup.retention.{key}] must be a non-negative integer")


def _validate_source_backup(
    src_backup: dict, source_name: str, result: ValidationResult
) -> None:
    priority = src_backup.get("priority", "normal")
    if priority not in VALID_PRIORITIES:
        result.add_error(
            f"[sources.{source_name}.backup] invalid priority '{priority}'; "
            f"must be one of: {', '.join(VALID_PRIORITIES)}"
        )

    if src_backup.get("include_db"):
        db = src_backup.get("db", {})
        if not db:
            result.add_error(
                f"[sources.{source_name}.backup] include_db is true but no 'db' block provided"
            )
        else:
            db_type = db.get("type")
            if db_type not in VALID_DB_TYPES:
                result.add_error(
                    f"[sources.{source_name}.backup.db] invalid type '{db_type}'; "
                    f"must be one of: {', '.join(VALID_DB_TYPES)}"
                )
            if not db.get("name"):
                result.add_error(
                    f"[sources.{source_name}.backup.db] missing required key 'name'"
                )


def _validate_source(src: dict, idx: int, result: ValidationResult) -> None:
    name = src.get("name", f"<source[{idx}]>")
    section = f"sources[{idx}] ({name!r})"

    src_type = _require(src, "type", section, result)
    _require(src, "path", section, result)

    if src_type not in ("local", "remote"):
        result.add_error(
            f"[{section}] invalid type '{src_type}'; must be 'local' or 'remote'"
        )

    if src_type == "remote":
        for key in ("host", "user"):
            _require(src, key, section, result)

    if not src.get("include"):
        result.add_warning(
            f"[{section}] no 'include' patterns defined; no docs will be collected"
        )

    if "backup" in src:
        _validate_source_backup(src["backup"], name, result)


def _check_duplicate_source_names(
    sources: list[dict], result: ValidationResult
) -> None:
    """Flag duplicate source names as an error — they cause manifest key collisions
    and silently merge nav entries, leading to data loss."""
    seen: dict[str, int] = {}
    for i, src in enumerate(sources):
        name = src.get("name", f"<source[{i}]>")
        if name in seen:
            result.add_error(
                f"[sources] duplicate source name '{name}' "
                f"(also defined at index {seen[name]})"
            )
        else:
            seen[name] = i


def _check_overlapping_sources(sources: list[dict], result: ValidationResult) -> None:
    paths: dict[str, str] = {}
    for src in sources:
        path = src.get("path", "")
        name = src.get("name", path)
        src_type = src.get("type", "local")
        if src_type == "local" and path:
            key = str(Path(path).resolve()) if Path(path).exists() else path
            if key in paths:
                result.add_warning(
                    f"Overlapping source paths: '{name}' and '{paths[key]}' "
                    f"both reference '{path}'"
                )
            else:
                paths[key] = name


# ── Runtime checks (connectivity, filesystem) ─────────────────────────────────


def check_local_paths(config: dict, result: ValidationResult) -> None:
    """Verify local source paths exist on the filesystem."""
    for src in config.get("sources", []):
        if src.get("type") != "local":
            continue
        name = src.get("name", src.get("path", "?"))
        path = src.get("path")
        if path:
            resolved = _resolve_path(path)
            if not resolved.exists():
                result.add_error(
                    f"[source: {name!r}] local path does not exist: {resolved}"
                )
            elif not resolved.is_dir():
                result.add_error(
                    f"[source: {name!r}] path is not a directory: {resolved}"
                )


def check_backup_base_dir(config: dict, result: ValidationResult) -> None:
    """Verify the backup base_dir exists and is writable (or can be created)."""
    backup = config.get("backup", {})
    if not backup.get("enabled", True):
        return
    base_dir_str = backup.get("base_dir")
    if not base_dir_str:
        return
    base_dir = _resolve_path(base_dir_str)
    if base_dir.exists():
        if not os.access(base_dir, os.W_OK):
            result.add_error(f"[backup.base_dir] directory is not writable: {base_dir}")
    else:
        # Check if the parent is writable so we could create it
        parent = base_dir.parent
        if parent.exists() and not os.access(parent, os.W_OK):
            result.add_error(
                f"[backup.base_dir] cannot create directory (parent not writable): {base_dir}"
            )
        else:
            result.add_warning(
                f"[backup.base_dir] directory does not exist and will be created: {base_dir}"
            )


def check_ssh_connectivity(config: dict, result: ValidationResult) -> None:
    """Test SSH connectivity for remote sources."""
    for src in config.get("sources", []):
        if src.get("type") != "remote":
            continue

        name = src.get("name", src.get("host", "?"))
        host = src.get("host", "")
        user = src.get("user", "")
        port = src.get("port", 22)
        key = src.get("key")
        strict_host_checking = src.get("strict_host_checking", False)

        if not host or not user:
            continue  # schema error already recorded

        host_key_opt = (
            "StrictHostKeyChecking=yes"
            if strict_host_checking
            else "StrictHostKeyChecking=no"
        )

        cmd = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=5",
            "-o",
            host_key_opt,
            "-p",
            str(port),
        ]
        if key:
            cmd += ["-i", str(_resolve_path(key))]
        cmd += [f"{user}@{host}", "true"]

        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=10)
            if proc.returncode != 0:
                stderr = proc.stderr.decode(errors="replace").strip()
                result.add_error(
                    f"[source: {name!r}] SSH connection failed "
                    f"({user}@{host}:{port}): {stderr or 'non-zero exit'}"
                )
        except subprocess.TimeoutExpired:
            result.add_error(
                f"[source: {name!r}] SSH connection timed out ({user}@{host}:{port})"
            )
        except FileNotFoundError:
            result.add_error(
                "[connectivity check] 'ssh' binary not found; cannot test remote sources"
            )
            break  # no point testing others


# ── Public API ────────────────────────────────────────────────────────────────


def load_config(path: Optional[Path] = None) -> dict:
    """Load and return the raw config dict from docsync.yaml.

    Raises ConfigError if the file cannot be read or parsed.
    """
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    config_path = config_path.expanduser().resolve()

    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    try:
        with open(config_path) as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config file must be a YAML mapping, got: {type(data).__name__}"
        )

    return data


def validate_config(config: dict) -> ValidationResult:
    """Run schema validation on the loaded config dict.

    Returns a ValidationResult with any errors or warnings found.
    Does NOT test connectivity or filesystem access — call the check_*
    functions separately for those.
    """
    result = ValidationResult()

    if "site" in config:
        _validate_site(config["site"], result)
    else:
        result.add_warning("[site] section missing; using defaults")

    if "sync" in config:
        _validate_sync(config["sync"], result)

    if "backup" in config:
        _validate_backup_global(config["backup"], result)

    sources = config.get("sources", [])
    if not sources:
        result.add_warning("[sources] no sources defined")
    else:
        for i, src in enumerate(sources):
            _validate_source(src, i, result)
        _check_duplicate_source_names(sources, result)
        _check_overlapping_sources(sources, result)

    return result


def load_and_validate(path: Optional[Path] = None) -> tuple[dict, ValidationResult]:
    """Load config and run schema validation. Raises ConfigError on parse failure."""
    config = load_config(path)
    result = validate_config(config)
    return config, result


def get_source_paths(config: dict) -> dict[str, Path]:
    """Return a dict mapping source names to their resolved root paths."""
    from pathlib import Path

    sources = config.get("sources", [])
    paths: dict[str, Path] = {}
    for src in sources:
        name = src.get("name", "")
        if not name:
            continue
        # Local sources use 'path', remote sources use staging
        if src.get("type") == "remote":
            continue
        paths[name] = Path(src.get("path", "")).expanduser().resolve()
    return paths
