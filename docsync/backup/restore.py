"""Snapshot and single-file restore."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .snapshot import list_snapshots, SNAPSHOT_META_FILE

log = logging.getLogger(__name__)


def restore_snapshot(
    source_backup_dir: Path,
    snapshot_name: str,
    dest: Optional[Path] = None,
    source: Optional[dict] = None,
) -> tuple[bool, str]:
    """Restore a full snapshot to *dest* (or original source path).

    Returns (success, message).
    """
    snap_dir = source_backup_dir / snapshot_name
    if not snap_dir.exists():
        return False, f"Snapshot not found: {snapshot_name}"

    if dest is None and source:
        dest = Path(source.get("path", "")).expanduser()

    if dest is None:
        return False, "No destination path — pass --dest or ensure source config has a path"

    dest.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rsync", "-a", "--delete",
        f"--exclude={SNAPSHOT_META_FILE}",
        str(snap_dir).rstrip("/") + "/",
        str(dest).rstrip("/") + "/",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
        if proc.returncode != 0:
            err = proc.stderr.decode(errors="replace").strip()
            return False, f"Restore failed: {err}"
    except subprocess.TimeoutExpired:
        return False, "Restore timed out"
    except FileNotFoundError:
        return False, "rsync not found"

    return True, f"Restored {snapshot_name} → {dest}"


def restore_file(
    source_backup_dir: Path,
    snapshot_name: str,
    file_rel_path: str,
    dest: Optional[Path] = None,
) -> tuple[bool, str]:
    """Restore a single file from a snapshot.

    Returns (success, message).
    """
    snap_dir = source_backup_dir / snapshot_name
    src_file = snap_dir / file_rel_path
    if not src_file.exists():
        return False, f"File not found in snapshot: {file_rel_path}"

    out = dest or Path(file_rel_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, out)
    return True, f"Restored {file_rel_path} → {out}"
