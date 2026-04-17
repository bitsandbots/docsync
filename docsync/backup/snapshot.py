"""Snapshot creation using rsync --link-dest for space-efficient incrementals."""

import json
import logging
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..utils import resolve_path

log = logging.getLogger(__name__)

SNAPSHOT_META_FILE = ".docsync-snapshot.json"
TIMESTAMP_FMT = "%Y-%m-%dT%H-%M-%S"


def timestamp_now() -> str:
    return datetime.now(timezone.utc).strftime(TIMESTAMP_FMT)


def parse_timestamp(ts: str) -> Optional[datetime]:
    try:
        return datetime.strptime(ts, TIMESTAMP_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def list_snapshots(source_backup_dir: Path) -> list[str]:
    """Return snapshot directory names sorted oldest→newest."""
    snaps = [
        d.name
        for d in source_backup_dir.iterdir()
        if d.is_dir() and parse_timestamp(d.name) is not None
    ]
    return sorted(snaps)


def latest_snapshot(source_backup_dir: Path) -> Optional[Path]:
    snaps = list_snapshots(source_backup_dir)
    return source_backup_dir / snaps[-1] if snaps else None


def _write_metadata(snapshot_dir: Path, meta: dict) -> None:
    # Ensure the snapshot dir is writable — rsync -a may have synced read-only
    # permissions from the source directory onto the snapshot directory itself.
    snapshot_dir.chmod(snapshot_dir.stat().st_mode | 0o300)
    (snapshot_dir / SNAPSHOT_META_FILE).write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )


def _read_metadata(snapshot_dir: Path) -> dict:
    p = snapshot_dir / SNAPSHOT_META_FILE
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _build_exclude_file(excludes: list[str]) -> str:
    """Write excludes to a temp file; returns its path."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="docsync-excl-"
    ) as fh:
        for pat in excludes:
            fh.write(pat + "\n")
        return fh.name


def _count_files(directory: Path) -> int:
    count = 0
    for entry in directory.rglob("*"):
        try:
            if entry.is_file() and entry.name != SNAPSHOT_META_FILE:
                count += 1
        except OSError:
            pass
    return count


def _dir_size(directory: Path) -> int:
    """Return apparent logical size of the snapshot in bytes.

    Hardlinked files (unchanged from a previous snapshot) are counted at their
    full logical size — this represents the data *accessible* in the snapshot,
    not the additional disk space consumed by it.
    """
    total = 0
    for f in directory.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def _new_bytes(snapshot_dir: Path, link_dest: Optional[Path]) -> int:
    """Return bytes of files that are NOT hardlinked from *link_dest*.

    This is the actual new disk space consumed by an incremental snapshot.
    For a full snapshot (link_dest is None) this equals _dir_size().
    """
    if link_dest is None:
        return _dir_size(snapshot_dir)

    # Collect inodes present in the previous snapshot to identify hardlinks.
    prev_inodes: set[int] = set()
    if link_dest.exists():
        for f in link_dest.rglob("*"):
            try:
                if f.is_file():
                    prev_inodes.add(f.stat().st_ino)
            except OSError:
                pass

    total = 0
    for f in snapshot_dir.rglob("*"):
        try:
            if f.is_file():
                st = f.stat()
                if st.st_ino not in prev_inodes:
                    total += st.st_size
        except OSError:
            pass
    return total


def create_snapshot(
    source: dict,
    source_backup_dir: Path,
    strategy: str = "incremental",
    extra_excludes: Optional[list[str]] = None,
) -> dict:
    """Create a new snapshot for *source* in *source_backup_dir*.

    Returns a metadata dict describing the snapshot result.
    """
    name = source["name"]
    src_type = source.get("type", "local")
    ts = timestamp_now()
    source_backup_dir.mkdir(parents=True, exist_ok=True)

    # Guard against same-second timestamp collision: append a counter so the
    # new snapshot always gets a unique directory distinct from link_dest.
    snapshot_dir = source_backup_dir / ts
    _col = 1
    while snapshot_dir.exists():
        snapshot_dir = source_backup_dir / f"{ts}_{_col}"
        _col += 1
    ts = snapshot_dir.name

    t0 = time.monotonic()

    # Find previous snapshot BEFORE creating the new directory
    link_dest: Optional[Path] = None
    if strategy == "incremental":
        prev = latest_snapshot(source_backup_dir)
        if prev:
            link_dest = prev

    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Build exclude patterns
    all_excludes: list[str] = list(extra_excludes or [])
    all_excludes += source.get("backup", {}).get("exclude", [])
    all_excludes.append(SNAPSHOT_META_FILE)

    excl_file = _build_exclude_file(all_excludes)

    # Build rsync command
    if src_type == "local":
        src_path = resolve_path(source["path"])
        src_arg = str(src_path).rstrip("/") + "/"
        ssh_prefix: list[str] = []
    else:
        host = source["host"]
        user = source["user"]
        port = source.get("port", 22)
        key = source.get("key")
        strict_host_checking = source.get("strict_host_checking", False)
        host_key_opt = (
            "StrictHostKeyChecking=yes"
            if strict_host_checking
            else "StrictHostKeyChecking=no"
        )
        ssh_opts = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            host_key_opt,
            "-p",
            str(port),
        ]
        if key:
            ssh_opts += ["-i", str(resolve_path(key))]
        src_arg = f"{user}@{host}:{source['path'].rstrip('/')}/"
        ssh_prefix = ["-e", " ".join(ssh_opts)]

    cmd = ["rsync", "-a", "--delete", "--timeout=300", f"--exclude-from={excl_file}"]
    if ssh_prefix:
        cmd += ssh_prefix
    if link_dest:
        cmd += [f"--link-dest={link_dest}"]
    cmd += [src_arg, str(snapshot_dir) + "/"]

    log.info(
        "[%s] creating snapshot %s%s",
        name,
        ts,
        " (incremental)" if link_dest else " (full)",
    )

    error_msg: Optional[str] = None
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=1200)
        if proc.returncode not in (0, 24):  # 24 = partial (vanished files) — OK
            error_msg = proc.stderr.decode(errors="replace").strip()
            log.error("[%s] rsync error: %s", name, error_msg)
    except subprocess.TimeoutExpired:
        error_msg = "rsync timed out after 600s"
    except FileNotFoundError:
        error_msg = "rsync binary not found"

    duration = time.monotonic() - t0

    # Remove failed/empty snapshot
    if error_msg:
        import shutil

        try:
            shutil.rmtree(snapshot_dir)
        except OSError:
            pass

    try:
        import os

        os.unlink(excl_file)
    except OSError:
        pass

    meta = {
        "timestamp": ts,
        "source_name": name,
        "status": "failed" if error_msg else "ok",
        "error": error_msg,
        "strategy": strategy,
        "link_dest": str(link_dest) if link_dest else None,
        "duration_seconds": round(duration, 2),
        "file_count": _count_files(snapshot_dir) if not error_msg else 0,
        "size_bytes": _dir_size(snapshot_dir) if not error_msg else 0,
        "new_bytes": _new_bytes(snapshot_dir, link_dest) if not error_msg else 0,
        "snapshot_dir": str(snapshot_dir) if not error_msg else None,
    }

    if not error_msg:
        _write_metadata(snapshot_dir, meta)
        # Update 'latest' symlink
        latest_link = source_backup_dir / "latest"
        if latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(ts)

    return meta
