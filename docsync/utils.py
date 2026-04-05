"""Shared helpers for DocSync."""

import hashlib
import os
import shutil
from pathlib import Path


def sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path, mode: int = 0o755) -> Path:
    """Create directory (and parents) if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    return path


def human_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def which_or_error(binary: str) -> str:
    """Return the full path to *binary* or raise RuntimeError if not found."""
    path = shutil.which(binary)
    if path is None:
        raise RuntimeError(
            f"Required binary '{binary}' not found in PATH. "
            f"Please install it before running DocSync."
        )
    return path


def resolve_path(p: str) -> Path:
    """Expand ~ and env vars, then resolve to an absolute path."""
    return Path(os.path.expandvars(os.path.expanduser(p))).resolve()
