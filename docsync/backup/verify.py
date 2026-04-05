"""Post-backup integrity verification via checksums."""

import logging
from pathlib import Path

from ..utils import sha256_file
from .snapshot import SNAPSHOT_META_FILE, _read_metadata

log = logging.getLogger(__name__)


def verify_snapshot(snapshot_dir: Path) -> tuple[bool, list[str]]:
    """Verify all files in *snapshot_dir* are readable (spot-check via SHA-256).

    Returns (all_ok, list_of_errors).
    """
    errors: list[str] = []
    meta = _read_metadata(snapshot_dir)
    expected_count = meta.get("file_count", 0)

    actual_count = 0
    for f in snapshot_dir.rglob("*"):
        if not f.is_file() or f.name == SNAPSHOT_META_FILE:
            continue
        try:
            sha256_file(f)  # reads every byte — catches I/O errors
            actual_count += 1
        except OSError as exc:
            errors.append(f"Cannot read {f.relative_to(snapshot_dir)}: {exc}")

    if expected_count and actual_count != expected_count:
        errors.append(
            f"File count mismatch: expected {expected_count}, found {actual_count}"
        )

    return not bool(errors), errors
