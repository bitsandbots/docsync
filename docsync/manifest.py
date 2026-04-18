"""File hash manifest — tracks SHA-256 checksums and sync timestamps.

The manifest is stored at ~/.cache/docsync/manifest.json and maps
each collected file path (relative to source root) to its last-known
hash and sync timestamp. Only changed files are re-processed.
"""

import fcntl
import json
import time
from pathlib import Path
from typing import Optional

from .utils import sha256_file

DEFAULT_MANIFEST_PATH = Path("~/.cache/docsync/manifest.json").expanduser()


class Manifest:
    """Persistent dict of {source_name/rel_path -> {hash, synced_at}}.

    Uses file locking to prevent corruption from concurrent processes.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else DEFAULT_MANIFEST_PATH
        self._data: dict[str, dict] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            try:
                with open(self._path) as fh:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_SH)
                    try:
                        self._data = json.load(fh)
                    finally:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        """Persist the manifest to disk with exclusive locking."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(self._data, fh, indent=2)
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        tmp.replace(self._path)

    # ── Change detection ──────────────────────────────────────────────────────

    def _key(self, source_name: str, rel_path: str) -> str:
        return f"{source_name}/{rel_path}"

    def get_hash(self, source_name: str, rel_path: str) -> Optional[str]:
        """Return the stored hash for this file, or None if not seen before."""
        return self._data.get(self._key(source_name, rel_path), {}).get("hash")

    def is_changed(self, source_name: str, rel_path: str, file_path: Path) -> bool:
        """Return True if the file is new or its content has changed."""
        stored = self.get_hash(source_name, rel_path)
        if stored is None:
            return True
        return sha256_file(file_path) != stored

    def update(
        self,
        source_name: str,
        rel_path: str,
        file_path: Path,
        *,
        title: str = "",
        description: str = "",
        tags: Optional[list] = None,
        order: int = 9999,
    ) -> str:
        """Record the current hash for a file and return it.

        Optional keyword args cache doc metadata so the nav can be rebuilt
        from the manifest without re-parsing files from disk.
        """
        digest = sha256_file(file_path)
        entry: dict = {"hash": digest, "synced_at": time.time()}
        if title:
            entry["title"] = title
        if description:
            entry["description"] = description
        if tags:
            entry["tags"] = tags
        if order != 9999:
            entry["order"] = order
        self._data[self._key(source_name, rel_path)] = entry
        return digest

    def remove_source(self, source_name: str) -> None:
        """Remove all manifest entries for a source."""
        prefix = f"{source_name}/"
        self._data = {k: v for k, v in self._data.items() if not k.startswith(prefix)}

    def remove_file(self, source_name: str, rel_path: str) -> None:
        """Remove a single file entry from the manifest."""
        key = self._key(source_name, rel_path)
        self._data.pop(key, None)

    def source_keys(self, source_name: str) -> list[str]:
        """Return all rel_paths known for a source."""
        prefix = f"{source_name}/"
        return [k[len(prefix) :] for k in self._data if k.startswith(prefix)]

    @property
    def path(self) -> Path:
        return self._path
