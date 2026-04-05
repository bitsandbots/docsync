"""Backup status and storage usage reporting."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from ..utils import human_size
from .snapshot import (
    list_snapshots,
    parse_timestamp,
    _read_metadata,
    _dir_size,
)

_STALE_HOURS = 36  # warn if latest snapshot older than this


def _source_slug(name: str) -> str:
    return re.sub(r"[^\w-]", "-", name.lower()).strip("-")


def source_backup_dir(base_dir: Path, source_name: str) -> Path:
    return base_dir / _source_slug(source_name)


def _ts_human(ts: Optional[str]) -> str:
    """Format a snapshot timestamp as a readable string, or 'Never'."""
    if not ts:
        return "Never"
    dt = parse_timestamp(ts)
    if dt is None:
        return ts
    return dt.strftime("%Y-%m-%d %H:%M")


def _compute_health(snap_count: int, latest_ts: Optional[str], latest_status: str) -> str:
    """Return 'ok', 'warn', or 'err'."""
    if latest_status == "failed":
        return "err"
    if snap_count == 0:
        return "warn"
    if latest_ts:
        dt = parse_timestamp(latest_ts)
        if dt:
            age = datetime.now(timezone.utc) - dt
            if age > timedelta(hours=_STALE_HOURS):
                return "warn"
    return "ok"


def backup_status(config: dict) -> list[dict]:
    """Return an enriched status dict for each backup-enabled source."""
    base = config.get("backup", {}).get("base_dir")
    if not base:
        return []
    base_dir = Path(base).expanduser()

    results = []
    for src in config.get("sources", []):
        if not src.get("backup", {}).get("enabled", True):
            continue

        name = src["name"]
        slug = _source_slug(name)
        src_dir = source_backup_dir(base_dir, name)
        snaps = list_snapshots(src_dir) if src_dir.exists() else []

        last_snap_meta: dict = {}
        if snaps:
            last_snap_meta = _read_metadata(src_dir / snaps[-1])

        total_size = sum(
            _dir_size(src_dir / s) for s in snaps
        ) if snaps else 0

        latest_ts = snaps[-1] if snaps else None
        latest_status = last_snap_meta.get("status", "unknown")

        results.append({
            "source_name": name,
            "slug": slug,
            "snapshot_count": len(snaps),
            "latest_snapshot": latest_ts,
            "latest_ts_human": _ts_human(latest_ts),
            "latest_status": latest_status,
            "latest_duration": last_snap_meta.get("duration_seconds"),
            "latest_file_count": last_snap_meta.get("file_count", 0),
            "total_size_bytes": total_size,
            "total_size_human": human_size(total_size),
            "health": _compute_health(len(snaps), latest_ts, latest_status),
            "snapshot_url": f"backups/{slug}.html",
        })

    return results


def recent_backup_events(config: dict, n: int = 20) -> list[dict]:
    """Return the last *n* backup log events, newest first."""
    base = config.get("backup", {}).get("base_dir")
    if not base:
        return []
    log_path = Path(base).expanduser() / "_global" / "backup-log.jsonl"
    if not log_path.exists():
        return []
    try:
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        events = []
        for line in lines:
            try:
                evt = json.loads(line)
                # Add human-readable timestamp
                raw_ts = evt.get("ts", "")
                try:
                    dt = datetime.fromisoformat(raw_ts)
                    evt["ts_human"] = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    evt["ts_human"] = raw_ts
                events.append(evt)
            except json.JSONDecodeError:
                pass
        return list(reversed(events[-n:]))
    except OSError:
        return []


def backup_status_json(config: dict, output_dir: Path) -> None:
    """Write backup-status.json to the site output directory."""
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": backup_status(config),
    }
    out = output_dir / "backup-status.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")


def snapshot_list(source_backup_dir: Path) -> list[dict]:
    """Return metadata for all snapshots of a source, newest first."""
    snaps = list_snapshots(source_backup_dir)
    result = []
    for name in reversed(snaps):
        meta = _read_metadata(source_backup_dir / name)
        if not meta:
            meta = {"timestamp": name, "status": "unknown"}
        # Add human-readable fields
        meta["ts_human"] = _ts_human(meta.get("timestamp"))
        size = meta.get("size_bytes", 0)
        meta["size_human"] = human_size(size) if size else "—"
        result.append(meta)
    return result
