#!/usr/bin/env python3
"""Health check for DocSync remote sources.

Tests SSH connectivity, validates paths, and reports sync status.

Usage:
    python remote-health-check.py
    python remote-health-check.py --config /path/to/config.yaml
    python remote-health-check.py --json
    python remote-health-check.py --source "Source Name"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class HealthResult:
    name: str
    host: str
    user: str
    path: str
    ssh_ok: bool = False
    ssh_error: str = ""
    path_exists: bool = False
    path_error: str = ""
    rsync_ok: bool = False
    rsync_error: str = ""
    last_sync: Optional[str] = None
    backup_count: int = 0
    issues: list[str] = field(default_factory=list)

    def is_healthy(self) -> bool:
        return self.ssh_ok and self.rsync_ok


def test_ssh_connection(source: dict) -> tuple[bool, str]:
    """Test SSH connectivity."""
    host = source.get("host", "")
    user = source.get("user", "")
    key = source.get("key", "~/.ssh/id_ed25519")

    if not host or not user:
        return False, "Missing host or user"

    key_path = Path(key).expanduser()
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=no",
        "-i",
        str(key_path),
        f"{user}@{host}",
        "echo 'SSH_OK'",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            return True, ""
        return (
            False,
            result.stderr.decode(errors="replace").strip() or "SSH connection failed",
        )
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
    except FileNotFoundError:
        return False, "SSH binary not found"
    except Exception as e:
        return False, str(e)


def test_remote_path(source: dict) -> tuple[bool, str]:
    """Test if the remote path exists and is readable."""
    host = source.get("host", "")
    user = source.get("user", "")
    path = source.get("path", "")
    key = source.get("key", "~/.ssh/id_ed25519")

    key_path = Path(key).expanduser()
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "StrictHostKeyChecking=no",
        "-i",
        str(key_path),
        f"{user}@{host}",
        f"test -d '{path}' && echo 'PATH_OK' || echo 'PATH_MISSING'",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        output = result.stdout.decode().strip()
        if output == "PATH_OK":
            return True, ""
        return False, f"Path does not exist: {path}"
    except Exception as e:
        return False, str(e)


def test_rsync_access(source: dict) -> tuple[bool, str]:
    """Test if rsync can list the remote path."""
    host = source.get("host", "")
    user = source.get("user", "")
    path = source.get("path", "")
    key = source.get("key", "~/.ssh/id_ed25519")

    key_path = Path(key).expanduser()
    rsync_url = f"{user}@{host}:{path}/"

    cmd = [
        "rsync",
        "--dry-run",
        "-avz",
        "-e",
        f"ssh -i {key_path} -o StrictHostKeyChecking=no",
        rsync_url,
        "/tmp/docsync-test/",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
        # rsync dry-run will fail if path doesn't exist, succeed if it does
        # A non-zero exit with "No such file" indicates path issue
        stderr = result.stderr.decode(errors="replace")
        if "No such file" in stderr:
            return False, "Path not accessible via rsync"
        if result.returncode == 0 or "sent" in stderr or "speedup" in stderr:
            return True, ""
        return False, stderr.strip() or "Rsync check failed"
    except subprocess.TimeoutExpired:
        return False, "Rsync timed out"
    except FileNotFoundError:
        return False, "rsync binary not found"
    except Exception as e:
        return False, str(e)


def get_backup_info(source_name: str, backup_dir: Path) -> tuple[Optional[str], int]:
    """Get last sync time and backup count for a source."""
    # This is a simplified check - could be enhanced with actual manifest data
    source_backup_dir = backup_dir / source_name.replace(" ", "_").lower()

    if not source_backup_dir.exists():
        return None, 0

    # Count snapshots (directories with timestamp names)
    snapshots = [d for d in source_backup_dir.iterdir() if d.is_dir()]

    # Get latest snapshot time
    last_sync = None
    if snapshots:
        latest = max(snapshots, key=lambda p: p.stat().st_mtime)
        last_sync = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()

    return last_sync, len(snapshots)


def check_source(source: dict, backup_dir: Optional[Path] = None) -> HealthResult:
    """Run all health checks on a remote source."""
    result = HealthResult(
        name=source.get("name", "unknown"),
        host=source.get("host", ""),
        user=source.get("user", ""),
        path=source.get("path", ""),
    )

    # Test SSH
    result.ssh_ok, result.ssh_error = test_ssh_connection(source)
    if not result.ssh_ok:
        result.issues.append(f"SSH: {result.ssh_error}")

    # If SSH works, test path and rsync
    if result.ssh_ok:
        result.path_exists, result.path_error = test_remote_path(source)
        if not result.path_exists:
            result.issues.append(f"Path: {result.path_error}")

        result.rsync_ok, result.rsync_error = test_rsync_access(source)
        if not result.rsync_ok:
            result.issues.append(f"Rsync: {result.rsync_error}")

    # Get backup info if configured
    if backup_dir and backup_dir.exists():
        result.last_sync, result.backup_count = get_backup_info(result.name, backup_dir)

    return result


def print_results(results: list[HealthResult], output_format: str = "table") -> None:
    """Print results in various formats."""
    if output_format == "json":
        print(json.dumps([asdict(r) for r in results], indent=2))
        return

    if output_format == "csv":
        print("name,host,ssh_ok,path_exists,rsync_ok,backup_count,issues")
        for r in results:
            issues = ";".join(r.issues) if r.issues else ""
            print(
                f"{r.name},{r.host},{r.ssh_ok},{r.path_exists},{r.rsync_ok},{r.backup_count},{issues}"
            )
        return

    # Table format
    print("")
    print(
        f"{'Source':<25} {'Host':<20} {'SSH':<8} {'Path':<8} {'Rsync':<8} {'Backups':<8}"
    )
    print("-" * 85)

    for r in results:
        ssh_status = "✓" if r.ssh_ok else "✗"
        path_status = "✓" if r.path_exists else "✗"
        rsync_status = "✓" if r.rsync_ok else "✗"

        print(
            f"{r.name:<25} {r.host:<20} {ssh_status:<8} {path_status:<8} {rsync_status:<8} {r.backup_count:<8}"
        )

        if r.issues:
            for issue in r.issues:
                print(f"    ⚠ {issue}")

    print("")

    # Summary
    total = len(results)
    healthy = sum(1 for r in results if r.is_healthy())
    unhealthy = total - healthy

    print(f"Summary: {healthy}/{total} sources healthy", end="")
    if unhealthy > 0:
        print(f" ({unhealthy} with issues)")
    else:
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Health check for DocSync remote sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("~/.config/docsync/docsync.yaml").expanduser(),
        help="Path to DocSync config file",
    )
    parser.add_argument(
        "--source",
        help="Check only this specific source by name",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        help="Backup base directory for checking backup status",
    )

    args = parser.parse_args()

    # Load config
    if not args.config.exists():
        print(f"Error: Config file not found: {args.config}")
        return 1

    with open(args.config) as f:
        config = yaml.safe_load(f) or {}

    sources = config.get("sources", [])
    if not sources:
        print("No sources configured.")
        return 0

    # Filter to remote sources
    remote_sources = [s for s in sources if s.get("type") == "remote"]

    # Filter to specific source if requested
    if args.source:
        remote_sources = [s for s in remote_sources if s.get("name") == args.source]
        if not remote_sources:
            print(f"Source not found: {args.source}")
            return 1

    if not remote_sources:
        print("No remote sources configured.")
        return 0

    # Determine backup dir
    backup_dir = args.backup_dir
    if not backup_dir and config.get("backup", {}).get("base_dir"):
        backup_dir = Path(config["backup"]["base_dir"]).expanduser()

    # Run checks
    print(f"Checking {len(remote_sources)} remote source(s)...")
    results = []
    for source in remote_sources:
        print(f"  Checking {source.get('name', 'unknown')}...", end="\r")
        result = check_source(source, backup_dir)
        results.append(result)
        print(" " * 50, end="\r")  # Clear line

    print_results(results, args.format)

    return 0 if all(r.is_healthy() for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
