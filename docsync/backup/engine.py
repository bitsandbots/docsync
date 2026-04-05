"""Core backup orchestration — runs snapshots, retention, and logging."""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .retention import RetentionPolicy, apply_retention
from .snapshot import create_snapshot
from .report import source_backup_dir

log = logging.getLogger(__name__)

BACKUP_LOG = "_global/backup-log.jsonl"


@dataclass
class BackupStats:
    sources_attempted: int = 0
    sources_succeeded: int = 0
    sources_failed: int = 0
    snapshots_pruned: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors


def _append_log(base_dir: Path, event: dict) -> None:
    log_path = base_dir / BACKUP_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as fh:
        fh.write(json.dumps(event) + "\n")


def _build_retention(config: dict) -> RetentionPolicy:
    ret = config.get("backup", {}).get("retention", {})
    return RetentionPolicy(
        daily=ret.get("daily", 7),
        weekly=ret.get("weekly", 4),
        monthly=ret.get("monthly", 6),
    )


def run_backup(
    config: dict,
    source_name: Optional[str] = None,
    force_full: bool = False,
) -> BackupStats:
    """Run backup for all (or one named) enabled source(s)."""
    t0 = time.monotonic()
    stats = BackupStats()

    backup_cfg = config.get("backup", {})
    if not backup_cfg.get("enabled", True):
        log.info("Backup disabled in config — skipping.")
        return stats

    base_dir_str = backup_cfg.get("base_dir")
    if not base_dir_str:
        stats.errors.append("backup.base_dir not configured")
        return stats

    base_dir = Path(base_dir_str).expanduser()
    base_dir.mkdir(parents=True, exist_ok=True)

    strategy = "full" if force_full else backup_cfg.get("strategy", "incremental")
    retention = _build_retention(config)

    sources = config.get("sources", [])
    if source_name:
        sources = [s for s in sources if s.get("name") == source_name]

    # Sort by priority: high first
    priority_order = {"high": 0, "normal": 1, "low": 2}
    sources = sorted(
        sources,
        key=lambda s: priority_order.get(s.get("backup", {}).get("priority", "normal"), 1),
    )

    for src in sources:
        bk_cfg = src.get("backup", {})
        if not bk_cfg.get("enabled", True):
            continue

        name = src["name"]
        src_backup_dir = source_backup_dir(base_dir, name)
        stats.sources_attempted += 1

        log.info("Backing up '%s'…", name)
        meta = create_snapshot(src, src_backup_dir, strategy=strategy)

        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": name,
            **meta,
        }
        _append_log(base_dir, event)

        if meta["status"] == "ok":
            stats.sources_succeeded += 1
            log.info(
                "'%s' snapshot %s complete: %d files, %s in %.1fs",
                name, meta["timestamp"],
                meta.get("file_count", 0),
                meta.get("size_bytes", 0),
                meta.get("duration_seconds", 0),
            )
            # Retention pruning
            pruned = apply_retention(src_backup_dir, retention)
            stats.snapshots_pruned += len(pruned)
        else:
            stats.sources_failed += 1
            err = f"[{name}] backup failed: {meta.get('error', 'unknown')}"
            stats.errors.append(err)
            log.error(err)

    stats.duration_seconds = time.monotonic() - t0
    return stats
