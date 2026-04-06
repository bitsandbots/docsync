"""Source collector — local glob matching and remote rsync/SSH staging."""

import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .manifest import Manifest
from .utils import resolve_path

STAGING_BASE = Path("~/.cache/docsync/staging").expanduser()

log = logging.getLogger(__name__)


@dataclass
class CollectedFile:
    """A single file collected from a source."""

    source_name: str
    abs_path: Path          # absolute path on local filesystem (or in staging dir)
    rel_path: str           # path relative to source root
    changed: bool           # True if content changed since last sync


@dataclass
class CollectResult:
    """Result of collecting one source."""

    source_name: str
    files: list[CollectedFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed_files(self) -> list[CollectedFile]:
        return [f for f in self.files if f.changed]

    @property
    def ok(self) -> bool:
        return not self.errors


def _glob_to_re(pattern: str) -> re.Pattern:
    """Convert a glob pattern (with ** support) to a compiled regex.

    Rules:
      **/ matches zero or more path components (e.g. docs/**/*.md)
      **  at end matches everything remaining (e.g. node_modules/**)
      *   matches any characters except '/'
      ?   matches one character except '/'
      No '/' in pattern: matches any file with that name anywhere in the tree
    """
    if "/" not in pattern:
        # bare filename pattern — match as filename component anywhere in path
        escaped = re.escape(pattern).replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        return re.compile(r"(?:^|.*/)(" + escaped + r")$")

    regex = ""
    i = 0
    while i < len(pattern):
        if pattern[i : i + 3] == "**/":
            regex += "(?:.+/)?"   # zero or more path components
            i += 3
        elif pattern[i : i + 2] == "**":
            regex += ".*"         # match anything to end (including slashes)
            i += 2
        elif pattern[i] == "*":
            regex += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            regex += "[^/]"
            i += 1
        else:
            regex += re.escape(pattern[i])
            i += 1

    return re.compile(r"^" + regex + r"$")


_GLOB_CACHE: dict[str, re.Pattern] = {}


def _matches_any(rel: str, patterns: list[str]) -> bool:
    """Return True if rel matches any glob pattern (supports ** for dirs)."""
    for pat in patterns:
        if pat not in _GLOB_CACHE:
            _GLOB_CACHE[pat] = _glob_to_re(pat)
        if _GLOB_CACHE[pat].search(rel):
            return True
    return False


def _collect_local(source: dict, manifest: Manifest) -> CollectResult:
    """Collect documentation files from a local source directory."""
    name: str = source["name"]
    root = Path(source["path"]).expanduser().resolve()
    include_pats: list[str] = source.get("include", ["**/*.md"])
    exclude_pats: list[str] = source.get("exclude", [])

    result = CollectResult(source_name=name)

    if not root.exists():
        result.errors.append(f"Path does not exist: {root}")
        return result

    # Walk the full tree; apply include/exclude filtering
    for abs_path in root.rglob("*"):
        if not abs_path.is_file():
            continue

        rel = abs_path.relative_to(root).as_posix()

        # Exclude check first (cheaper)
        if exclude_pats and _matches_any(rel, exclude_pats):
            continue

        # Include check
        if not _matches_any(rel, include_pats):
            continue

        changed = manifest.is_changed(name, rel, abs_path)
        result.files.append(
            CollectedFile(
                source_name=name,
                abs_path=abs_path,
                rel_path=rel,
                changed=changed,
            )
        )

    log.debug(
        "[%s] collected %d files (%d changed)",
        name,
        len(result.files),
        len(result.changed_files),
    )
    return result


def _build_ssh_opts(source: dict) -> list[str]:
    """Build SSH option flags for rsync -e."""
    port = source.get("port", 22)
    key = source.get("key")
    opts = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "-o", "GSSAPIAuthentication=no",
        "-o", "UseDNS=no",
        "-p", str(port),
    ]
    if key:
        opts += ["-i", str(resolve_path(key))]
    return opts


# Exit codes that indicate a connection-level failure — retrying won't help.
_SSH_FATAL_EXIT_CODES = {255}

# Hosts confirmed unreachable this run: skip further sources on the same host.
_dead_hosts: set[str] = set()


def _rsync_remote(source: dict, staging_dir: Path, retries: int = 2) -> Optional[str]:
    """Stage a remote source to *staging_dir* via rsync.

    Returns None on success, or an error string on failure.
    """
    host = source["host"]
    user = source["user"]
    remote_path = source["path"].rstrip("/") + "/"
    ssh_opts = " ".join(_build_ssh_opts(source))

    if host in _dead_hosts:
        return f"host {host!r} unreachable (skipped after earlier failure this run)"

    cmd = [
        "rsync",
        "-a",
        "--delete",
        "--timeout=30",
        "-e", ssh_opts,
        f"{user}@{host}:{remote_path}",
        str(staging_dir) + "/",
    ]

    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=45,
            )
            if proc.returncode == 0:
                return None
            stderr = proc.stderr.decode(errors="replace").strip()
            if proc.returncode in _SSH_FATAL_EXIT_CODES:
                _dead_hosts.add(host)
                return f"rsync failed (exit {proc.returncode}): {stderr}"
            if attempt < retries:
                log.warning(
                    "[%s] rsync attempt %d/%d failed (exit %d): %s — retrying…",
                    source.get("name"), attempt + 1, retries + 1,
                    proc.returncode, stderr,
                )
                time.sleep(2 ** attempt)  # 1s, 2s backoff
            else:
                return f"rsync failed (exit {proc.returncode}): {stderr}"
        except subprocess.TimeoutExpired:
            _dead_hosts.add(host)
            if attempt < retries:
                log.warning("[%s] rsync timed out — retrying…", source.get("name"))
            else:
                return "rsync timed out after 45s"
        except FileNotFoundError:
            return "rsync binary not found; install rsync to use remote sources"

    return "rsync failed after all retries"


def _collect_remote(source: dict, manifest: Manifest) -> CollectResult:
    """Stage a remote source locally via rsync, then collect using local logic."""
    name: str = source["name"]
    result = CollectResult(source_name=name)

    # Staging dir: ~/.cache/docsync/staging/<slugified-name>/
    slug = re.sub(r"[^\w-]", "-", name.lower()).strip("-")
    staging_dir = STAGING_BASE / slug
    staging_dir.mkdir(parents=True, exist_ok=True)

    log.info("[%s] staging remote source via rsync…", name)
    err = _rsync_remote(source, staging_dir)
    if err:
        result.errors.append(f"Remote staging failed: {err}")
        return result

    # Reuse local collection logic against the staging directory
    staged_source = {**source, "type": "local", "path": str(staging_dir)}
    return _collect_local(staged_source, manifest)


def collect_source(source: dict, manifest: Manifest) -> CollectResult:
    """Collect files for a single source config entry."""
    src_type = source.get("type", "local")
    if src_type == "local":
        return _collect_local(source, manifest)
    elif src_type == "remote":
        return _collect_remote(source, manifest)
    else:
        result = CollectResult(source_name=source.get("name", "?"))
        result.errors.append(f"Unknown source type: {src_type!r}")
        return result


def collect_all(
    config: dict,
    manifest: Manifest,
    source_name: Optional[str] = None,
) -> list[CollectResult]:
    """Collect all sources (or a single named source)."""
    _dead_hosts.clear()  # reset per-run host failure cache

    sources = config.get("sources", [])
    if source_name:
        sources = [s for s in sources if s.get("name") == source_name]
        if not sources:
            raise ValueError(f"No source named '{source_name}' found in config")

    results: list[CollectResult] = []
    for src in sources:
        results.append(collect_source(src, manifest))

    return results
