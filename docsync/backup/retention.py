"""Retention policy enforcement and snapshot pruning.

Keeps the N most recent daily snapshots, N weekly (one per week),
and N monthly (one per month). Everything outside the window is deleted.
Hardlinks mean deleting old snapshots only frees space for unique files.
"""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

from .snapshot import list_snapshots, parse_timestamp

log = logging.getLogger(__name__)


class RetentionPolicy(NamedTuple):
    daily: int = 7
    weekly: int = 4
    monthly: int = 6


def _week_key(dt: datetime) -> str:
    """ISO year + week number."""
    return dt.strftime("%G-W%V")


def _month_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def apply_retention(source_backup_dir: Path, policy: RetentionPolicy) -> list[str]:
    """Prune snapshots in *source_backup_dir* according to *policy*.

    Returns list of snapshot names that were deleted.
    """
    snap_names = list_snapshots(source_backup_dir)
    if not snap_names:
        return []

    # Parse timestamps newest→oldest
    dated: list[tuple[datetime, str]] = []
    for name in snap_names:
        dt = parse_timestamp(name)
        if dt:
            dated.append((dt, name))
    dated.sort(reverse=True)  # newest first

    keep: set[str] = set()

    # Daily: keep N most recent
    for _, name in dated[:policy.daily]:
        keep.add(name)

    # Weekly: for each distinct week, keep the newest snapshot in that week
    seen_weeks: dict[str, str] = {}
    for dt, name in dated:
        wk = _week_key(dt)
        if wk not in seen_weeks:
            seen_weeks[wk] = name
    for i, (wk, name) in enumerate(sorted(seen_weeks.items(), reverse=True)):
        if i < policy.weekly:
            keep.add(name)

    # Monthly: for each distinct month, keep the newest snapshot
    seen_months: dict[str, str] = {}
    for dt, name in dated:
        mo = _month_key(dt)
        if mo not in seen_months:
            seen_months[mo] = name
    for i, (mo, name) in enumerate(sorted(seen_months.items(), reverse=True)):
        if i < policy.monthly:
            keep.add(name)

    deleted: list[str] = []
    for _, name in dated:
        if name not in keep:
            snap_path = source_backup_dir / name
            try:
                shutil.rmtree(snap_path)
                deleted.append(name)
                log.info("pruned snapshot %s/%s", source_backup_dir.name, name)
            except OSError as exc:
                log.error("failed to prune %s: %s", snap_path, exc)

    return deleted
