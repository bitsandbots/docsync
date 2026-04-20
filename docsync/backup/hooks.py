"""Pre-backup hooks: DB dumps (MySQL, SQLite) via SSH or locally."""

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Optional

from ..utils import resolve_path

log = logging.getLogger(__name__)


def run_db_dump(source: dict, snapshot_dir: Path) -> Optional[str]:
    """Execute a DB dump for sources with include_db: true.

    Returns None on success, error string on failure.
    """
    bk = source.get("backup", {})
    if not bk.get("include_db"):
        return None

    db_cfg = bk.get("db", {})
    dump_cmd = db_cfg.get("dump_command", "")
    db_name = db_cfg.get("name", "db")

    if not dump_cmd:
        return "include_db is true but no dump_command configured"

    ext = "sql"
    out_file = snapshot_dir / f"{db_name}.{ext}.zst"

    src_type = source.get("type", "local")
    if src_type == "remote":
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
        ssh_cmd = [
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
            ssh_cmd += ["-i", str(resolve_path(key))]
        ssh_cmd.append(f"{user}@{host}")
        cmd = ssh_cmd + [dump_cmd]
    else:
        cmd = shlex.split(dump_cmd)

    try:
        import zstandard as zstd

        log.info("[%s] running DB dump: %s", source["name"], dump_cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cctx = zstd.ZstdCompressor()
        with open(out_file, "wb") as fh:
            for chunk in cctx.read_to_iter(proc.stdout):
                fh.write(chunk)
        proc.wait(timeout=120)
        if proc.returncode != 0:
            stderr = proc.stderr.read().decode(errors="replace").strip()
            return f"dump command failed (exit {proc.returncode}): {stderr}"
    except ImportError:
        # zstandard not available — fall back to uncompressed
        out_file = snapshot_dir / f"{db_name}.{ext}"
        try:
            with open(out_file, "wb") as fh:
                proc = subprocess.run(
                    cmd, stdout=fh, stderr=subprocess.PIPE, timeout=120
                )
            if proc.returncode != 0:
                return proc.stderr.decode(errors="replace").strip()
        except subprocess.TimeoutExpired:
            return "DB dump timed out"
    except subprocess.TimeoutExpired:
        return "DB dump timed out"
    except Exception as exc:
        return str(exc)

    return None
