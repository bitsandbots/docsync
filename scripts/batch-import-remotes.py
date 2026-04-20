#!/usr/bin/env python3
"""Batch import remote sources for DocSync from a CSV file.

Usage:
    python batch-import-remotes.py sources.csv
    python batch-import-remotes.py sources.csv --dry-run
    python batch-import-remotes.py sources.csv --config ~/.config/docsync/docsync.yaml

CSV format (header row required):
    name,host,user,path,category,icon,ssh_key

Example CSV:
    name,host,user,path,category,icon,ssh_key
    Web Server,192.168.1.10,pi,/var/www/web,Servers,server,~/.ssh/docsync_web
    Database Pi,192.168.1.11,pi,/opt/db,Servers,database,~/.ssh/docsync_db
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

import yaml


def generate_source_yaml(row: dict) -> dict:
    """Generate a DocSync source dict from CSV row data."""
    return {
        "name": row["name"],
        "type": "remote",
        "host": row["host"],
        "user": row["user"],
        "key": row.get("ssh_key", "~/.ssh/id_ed25519"),
        "path": row["path"],
        "strict_host_checking": False,
        "include": ["docs/**/*.md", "README.md", "CLAUDE.md", "AGENTS.md"],
        "exclude": [
            ".git/**",
            "node_modules/**",
            "__pycache__/**",
            ".pytest_cache/**",
            "venv/**",
            "*.egg-info/**",
        ],
        "category": row.get("category", "Projects"),
        "icon": row.get("icon", "document"),
        "backup": {
            "enabled": True,
            "include_all": True,
            "exclude": [".git/**", "node_modules/**", "__pycache__/**", "venv/**"],
            "priority": "normal",
        },
    }


def validate_ssh_connection(source: dict) -> tuple[bool, str]:
    """Test SSH connectivity to a remote source."""
    key_path = Path(source["key"]).expanduser()
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
        f"{source['user']}@{source['host']}",
        "echo 'SSH_OK'",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        if result.returncode == 0:
            return True, "OK"
        return False, result.stderr.decode(errors="replace").strip()
    except subprocess.TimeoutExpired:
        return False, "Connection timed out"
    except FileNotFoundError:
        return False, "SSH binary not found"
    except Exception as e:
        return False, str(e)


def load_config(config_path: Path) -> dict:
    """Load existing DocSync config."""
    with open(config_path) as f:
        return yaml.safe_load(f) or {}


def save_config(config_path: Path, config: dict) -> None:
    """Save config back to file with comments preserved where possible."""
    with open(config_path, "w") as f:
        yaml.dump(
            config, f, default_flow_style=False, sort_keys=False, allow_unicode=True
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch import remote sources for DocSync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s sources.csv --dry-run
  %(prog)s sources.csv --validate-ssh
  %(prog)s sources.csv --skip-existing
        """,
    )
    parser.add_argument("csv_file", help="CSV file with remote source definitions")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("~/.config/docsync/docsync.yaml").expanduser(),
        help="Path to DocSync config file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without modifying config",
    )
    parser.add_argument(
        "--validate-ssh",
        action="store_true",
        help="Test SSH connectivity for each source before adding",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip sources that already exist in config (by name)",
    )
    parser.add_argument(
        "--generate-keys",
        action="store_true",
        help="Generate SSH keys for sources that don't have them",
    )

    args = parser.parse_args()

    # Check CSV exists
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return 1

    # Check config exists
    if not args.config.exists():
        print(f"Error: DocSync config not found: {args.config}")
        print("Run 'docsync init' first to create a config file.")
        return 1

    # Load config
    config = load_config(args.config)
    existing_names = {src.get("name") for src in config.get("sources", [])}

    # Read CSV
    sources_to_add = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            if not row.get("name"):
                continue
            sources_to_add.append(row)

    print(f"\nFound {len(sources_to_add)} source(s) in CSV")
    print(f"Existing sources in config: {len(existing_names)}")
    print("")

    # Process each source
    added = 0
    skipped = 0
    failed = 0

    for row in sources_to_add:
        name = row["name"]

        # Check for duplicates
        if name in existing_names:
            if args.skip_existing:
                print(f"  ⏭  {name}: Already exists, skipping")
                skipped += 1
                continue
            else:
                print(
                    f"  ⚠  {name}: Already exists in config (use --skip-existing to ignore)"
                )
                failed += 1
                continue

        # Generate source YAML
        source = generate_source_yaml(row)

        # Validate SSH if requested
        if args.validate_ssh:
            print(f"  🔍 {name}: Testing SSH...", end=" ", flush=True)
            ok, msg = validate_ssh_connection(source)
            if ok:
                print("OK")
            else:
                print(f"FAILED ({msg})")
                failed += 1
                continue

        # Generate SSH key if requested and doesn't exist
        if args.generate_keys:
            key_path = Path(source["key"]).expanduser()
            if not key_path.exists():
                print(f"  🔑 {name}: Generating SSH key...", end=" ", flush=True)
                try:
                    subprocess.run(
                        [
                            "ssh-keygen",
                            "-t",
                            "ed25519",
                            "-C",
                            f"docsync-{name}",
                            "-f",
                            str(key_path),
                            "-N",
                            "",
                        ],
                        capture_output=True,
                        check=True,
                    )
                    print("OK")
                    # Show the public key
                    pub_key = key_path.with_suffix(".pub")
                    if pub_key.exists():
                        print(f"      Public key: {pub_key}")
                        print(
                            f"      Add to remote host: cat {pub_key} >> ~/.ssh/authorized_keys"
                        )
                except subprocess.CalledProcessError as e:
                    print(f"FAILED: {e}")
                    failed += 1
                    continue

        # Add to config
        if args.dry_run:
            print(f"  ✓  {name}: Would add (dry-run)")
        else:
            if "sources" not in config:
                config["sources"] = []
            config["sources"].append(source)
            existing_names.add(name)
            print(f"  ✓  {name}: Added")

        added += 1

    # Save config
    if not args.dry_run and added > 0:
        save_config(args.config, config)
        print(f"\n✓ Saved {added} source(s) to {args.config}")
    elif args.dry_run:
        print(f"\n(Dry-run mode: {added} source(s) would be added)")
    else:
        print("\nNo sources added.")

    # Summary
    print(f"\nSummary:")
    print(f"  Added:   {added}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
