"""Tests for backup engine: snapshot, retention, restore, verify, report."""

import json
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from docsync.backup.retention import RetentionPolicy, apply_retention
from docsync.backup.restore import restore_file, restore_snapshot
from docsync.backup.snapshot import (
    SNAPSHOT_META_FILE,
    create_snapshot,
    list_snapshots,
    latest_snapshot,
    parse_timestamp,
    timestamp_now,
)
from docsync.backup.verify import verify_snapshot


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_project(base: Path) -> Path:
    src = base / "project"
    src.mkdir()
    (src / "README.md").write_text("# Hello")
    (src / "src").mkdir()
    (src / "src" / "main.py").write_text("def main(): pass")
    return src


def make_fake_snapshot(snap_dir: Path, file_count: int = 3) -> None:
    snap_dir.mkdir(parents=True)
    for i in range(file_count):
        (snap_dir / f"file{i}.md").write_text(f"content {i}")
    meta = {
        "timestamp": snap_dir.name,
        "status": "ok",
        "file_count": file_count,
        "size_bytes": file_count * 10,
    }
    (snap_dir / SNAPSHOT_META_FILE).write_text(json.dumps(meta))


# ── parse_timestamp ───────────────────────────────────────────────────────────

def test_parse_timestamp_valid():
    dt = parse_timestamp("2026-04-05T02-00-00")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 4 and dt.day == 5


def test_parse_timestamp_invalid():
    assert parse_timestamp("not-a-timestamp") is None
    assert parse_timestamp("") is None


# ── list_snapshots ────────────────────────────────────────────────────────────

def test_list_snapshots_sorted(tmp_path):
    src_dir = tmp_path / "myproj"
    for ts in ["2026-04-03T02-00-00", "2026-04-05T02-00-00", "2026-04-04T02-00-00"]:
        make_fake_snapshot(src_dir / ts)
    snaps = list_snapshots(src_dir)
    assert snaps == ["2026-04-03T02-00-00", "2026-04-04T02-00-00", "2026-04-05T02-00-00"]


def test_list_snapshots_empty(tmp_path):
    (tmp_path / "empty").mkdir()
    assert list_snapshots(tmp_path / "empty") == []


# ── create_snapshot (local) ───────────────────────────────────────────────────

def test_create_snapshot_local(tmp_path):
    src = make_project(tmp_path)
    backup_dir = tmp_path / "backups" / "project"
    source = {"name": "project", "type": "local", "path": str(src)}

    meta = create_snapshot(source, backup_dir)
    assert meta["status"] == "ok"
    assert meta["file_count"] >= 2
    assert meta["snapshot_dir"] is not None
    snap_dir = Path(meta["snapshot_dir"])
    assert (snap_dir / "README.md").exists()


def test_create_snapshot_incremental_uses_link_dest(tmp_path):
    src = make_project(tmp_path)
    backup_dir = tmp_path / "backups" / "project"
    source = {"name": "project", "type": "local", "path": str(src)}

    meta1 = create_snapshot(source, backup_dir)
    assert meta1["status"] == "ok"
    assert meta1["link_dest"] is None  # first snapshot, no previous

    meta2 = create_snapshot(source, backup_dir)
    assert meta2["status"] == "ok"
    assert meta2["link_dest"] is not None  # incremental


def test_create_snapshot_missing_source_fails(tmp_path):
    backup_dir = tmp_path / "backups"
    source = {"name": "missing", "type": "local", "path": str(tmp_path / "nonexistent")}
    meta = create_snapshot(source, backup_dir)
    assert meta["status"] == "failed"


def test_create_snapshot_excludes_files(tmp_path):
    src = make_project(tmp_path)
    (src / "build").mkdir()
    (src / "build" / "artifact.bin").write_text("big binary")

    backup_dir = tmp_path / "backups" / "project"
    source = {
        "name": "project", "type": "local", "path": str(src),
        "backup": {"exclude": ["build/**"]},
    }
    meta = create_snapshot(source, backup_dir)
    assert meta["status"] == "ok"
    snap_dir = Path(meta["snapshot_dir"])
    assert not (snap_dir / "build" / "artifact.bin").exists()


def test_latest_symlink_created(tmp_path):
    src = make_project(tmp_path)
    backup_dir = tmp_path / "backups" / "project"
    source = {"name": "project", "type": "local", "path": str(src)}
    create_snapshot(source, backup_dir)
    assert (backup_dir / "latest").is_symlink()


# ── apply_retention ───────────────────────────────────────────────────────────

def make_timestamped_snaps(src_dir: Path, timestamps: list[str]) -> None:
    for ts in timestamps:
        make_fake_snapshot(src_dir / ts)


def test_retention_keeps_daily(tmp_path):
    src_dir = tmp_path / "proj"
    # 10 daily snapshots
    timestamps = [
        f"2026-04-{d:02d}T02-00-00" for d in range(1, 11)
    ]
    make_timestamped_snaps(src_dir, timestamps)
    policy = RetentionPolicy(daily=7, weekly=0, monthly=0)
    pruned = apply_retention(src_dir, policy)
    remaining = list_snapshots(src_dir)
    assert len(remaining) == 7
    assert len(pruned) == 3


def test_retention_keeps_weekly(tmp_path):
    src_dir = tmp_path / "proj"
    # Create one snapshot per day for 28 days (4 full weeks)
    base = datetime(2026, 3, 1, tzinfo=timezone.utc)
    timestamps = [
        (base + timedelta(days=i)).strftime("2026-%m-%dT02-00-00")
        for i in range(28)
    ]
    make_timestamped_snaps(src_dir, timestamps)
    policy = RetentionPolicy(daily=2, weekly=4, monthly=0)
    apply_retention(src_dir, policy)
    remaining = list_snapshots(src_dir)
    assert len(remaining) >= 2  # at least daily kept


def test_retention_empty_dir(tmp_path):
    src_dir = tmp_path / "proj"
    src_dir.mkdir()
    pruned = apply_retention(src_dir, RetentionPolicy())
    assert pruned == []


# ── restore ───────────────────────────────────────────────────────────────────

def test_restore_full_snapshot(tmp_path):
    snap_dir = tmp_path / "snaps" / "2026-04-05T02-00-00"
    make_fake_snapshot(snap_dir, file_count=3)
    dest = tmp_path / "restored"

    ok, msg = restore_snapshot(tmp_path / "snaps", "2026-04-05T02-00-00", dest)
    assert ok
    assert (dest / "file0.md").exists()
    # Metadata file should not be present in dest
    assert not (dest / SNAPSHOT_META_FILE).exists()


def test_restore_single_file(tmp_path):
    snap_dir = tmp_path / "snaps" / "2026-04-05T02-00-00"
    make_fake_snapshot(snap_dir, file_count=2)
    dest = tmp_path / "restored-file.md"

    ok, msg = restore_file(tmp_path / "snaps", "2026-04-05T02-00-00", "file0.md", dest)
    assert ok
    assert dest.exists()
    assert dest.read_text() == "content 0"


def test_restore_missing_snapshot(tmp_path):
    src_dir = tmp_path / "snaps"
    src_dir.mkdir()
    ok, msg = restore_snapshot(src_dir, "9999-01-01T00-00-00", tmp_path / "dest")
    assert not ok
    assert "not found" in msg.lower()


def test_restore_missing_file(tmp_path):
    snap_dir = tmp_path / "snaps" / "2026-04-05T02-00-00"
    make_fake_snapshot(snap_dir)
    ok, msg = restore_file(tmp_path / "snaps", "2026-04-05T02-00-00", "nonexistent.txt")
    assert not ok


# ── verify_snapshot ───────────────────────────────────────────────────────────

def test_verify_healthy_snapshot(tmp_path):
    snap_dir = tmp_path / "snaps" / "2026-04-05T02-00-00"
    make_fake_snapshot(snap_dir, file_count=3)
    ok, errors = verify_snapshot(snap_dir)
    assert ok
    assert not errors


def test_verify_detects_missing_file(tmp_path):
    snap_dir = tmp_path / "snaps" / "2026-04-05T02-00-00"
    make_fake_snapshot(snap_dir, file_count=3)
    # Remove a file after snapshot was made
    (snap_dir / "file1.md").unlink()
    ok, errors = verify_snapshot(snap_dir)
    assert not ok
    assert errors
