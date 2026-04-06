"""Click-based CLI entry point for DocSync."""

import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import (
    ConfigError,
    check_backup_base_dir,
    check_local_paths,
    check_ssh_connectivity,
    load_and_validate,
)
from .manifest import Manifest
from .generator import _PKG_DIR


# ── Shared context ────────────────────────────────────────────────────────────

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _echo_ok(msg: str) -> None:
    click.echo(click.style("  ✓ ", fg="green") + msg)


def _echo_warn(msg: str) -> None:
    click.echo(click.style("  ⚠ ", fg="yellow") + msg)


def _echo_err(msg: str) -> None:
    click.echo(click.style("  ✗ ", fg="red") + msg)


def _echo_section(title: str) -> None:
    click.echo(click.style(f"\n{title}", bold=True))
    click.echo("─" * len(title))


# ── Root group ────────────────────────────────────────────────────────────────

@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-V", "--version")
@click.option(
    "--config", "-c",
    type=click.Path(exists=False, path_type=Path),
    default=None,
    envvar="DOCSYNC_CONFIG",
    help="Path to docsync.yaml (default: ~/.config/docsync/docsync.yaml)",
)
@click.pass_context
def cli(ctx: click.Context, config: Path | None) -> None:
    """DocSync — project documentation wiki and file backup tool."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


# ── docsync check ─────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--no-ssh", is_flag=True, default=False,
    help="Skip SSH connectivity tests for remote sources.",
)
@click.pass_context
def check(ctx: click.Context, no_ssh: bool) -> None:
    """Validate config and test connectivity."""
    config_path: Path | None = ctx.obj.get("config_path")

    # ── Load & schema-validate ────────────────────────────────────────────────
    _echo_section("Loading config")
    try:
        config, result = load_and_validate(config_path)
    except ConfigError as exc:
        _echo_err(str(exc))
        sys.exit(1)

    resolved = (
        config_path.expanduser().resolve()
        if config_path
        else Path("~/.config/docsync/docsync.yaml").expanduser()
    )
    _echo_ok(f"Loaded: {resolved}")

    # ── Schema validation results ─────────────────────────────────────────────
    _echo_section("Schema validation")
    if result.ok() and not result.warnings:
        _echo_ok("No errors or warnings")
    else:
        for err in result.errors:
            _echo_err(err)
        for warn in result.warnings:
            _echo_warn(warn)

    # ── Local path checks ─────────────────────────────────────────────────────
    _echo_section("Local source paths")
    path_result = _fresh_result()
    check_local_paths(config, path_result)
    _print_result_detail(config, path_result, check_type="paths")

    # ── Backup base_dir ───────────────────────────────────────────────────────
    _echo_section("Backup base_dir")
    backup_result = _fresh_result()
    check_backup_base_dir(config, backup_result)
    _print_simple(backup_result, ok_msg="backup.base_dir is writable")

    # ── SSH connectivity ──────────────────────────────────────────────────────
    remote_sources = [s for s in config.get("sources", []) if s.get("type") == "remote"]
    if remote_sources and not no_ssh:
        _echo_section("SSH connectivity")
        ssh_result = _fresh_result()
        check_ssh_connectivity(config, ssh_result)
        _print_simple(
            ssh_result,
            ok_msg=f"All {len(remote_sources)} remote source(s) reachable",
        )
    elif no_ssh and remote_sources:
        _echo_section("SSH connectivity")
        _echo_warn(f"Skipped (--no-ssh); {len(remote_sources)} remote source(s) not tested")

    # ── Summary ───────────────────────────────────────────────────────────────
    _echo_section("Summary")
    all_errors = (
        result.errors
        + path_result.errors
        + backup_result.errors
    )
    if remote_sources and not no_ssh:
        all_errors += ssh_result.errors

    all_warnings = (
        result.warnings
        + path_result.warnings
        + backup_result.warnings
    )

    if all_errors:
        click.echo(
            click.style(f"  {len(all_errors)} error(s) found — fix before running docsync.", fg="red", bold=True)
        )
        sys.exit(1)
    elif all_warnings:
        click.echo(
            click.style(f"  {len(all_warnings)} warning(s) — config is usable but review above.", fg="yellow")
        )
    else:
        click.echo(click.style("  All checks passed.", fg="green", bold=True))


# ── docsync sync ──────────────────────────────────────────────────────────────

@cli.command()
@click.option("--source", "-s", default=None, help="Sync a single named source.")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Show per-file details.")
@click.pass_context
def sync(ctx: click.Context, source: str | None, verbose: bool) -> None:
    """Run a full documentation sync."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
        # Suppress noisy markdown-it internal debug output
        logging.getLogger("markdown_it").setLevel(logging.WARNING)

    config_path: Path | None = ctx.obj.get("config_path")
    try:
        config, result = load_and_validate(config_path)
    except ConfigError as exc:
        _echo_err(str(exc))
        sys.exit(1)

    if not result.ok():
        for err in result.errors:
            _echo_err(err)
        sys.exit(1)

    from .sync import run_sync

    manifest = Manifest()
    label = f"source '{source}'" if source else "all sources"
    click.echo(click.style(f"Syncing {label}…", bold=True))

    try:
        stats, docs = run_sync(config, manifest, source_name=source)
    except Exception as exc:
        _echo_err(f"Sync failed: {exc}")
        sys.exit(1)

    if stats.errors:
        for err in stats.errors:
            _echo_err(err)

    click.echo(
        f"  Sources: {stats.sources_processed}"
        + (f" ({stats.sources_skipped} skipped)" if stats.sources_skipped else "")
    )
    click.echo(f"  Files collected: {stats.files_collected}")
    click.echo(f"  Files changed:   {stats.files_changed}")
    click.echo(f"  Files parsed:    {stats.files_parsed}")
    click.echo(f"  Pages generated: {stats.pages_generated}")
    click.echo(f"  Duration:        {stats.duration_seconds:.2f}s")

    if verbose and docs:
        _echo_section("Parsed docs")
        for doc in docs:
            click.echo(f"  {doc.rel_path}  →  {doc.title!r}  ({len(doc.toc)} headings)")

    if stats.ok:
        click.echo(click.style("  Sync complete.", fg="green", bold=True))
    else:
        click.echo(click.style("  Sync completed with errors.", fg="yellow"))
        sys.exit(1)


# ── docsync status ────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show last sync time, file counts, and manifest state."""
    import json

    manifest = Manifest()
    if not manifest.path.exists():
        click.echo("No manifest found — run `docsync sync` first.")
        return

    with open(manifest.path) as fh:
        data = json.load(fh)

    if not data:
        click.echo("Manifest is empty.")
        return

    # Group by source
    sources: dict[str, list] = {}
    latest_ts = 0.0
    for key, val in data.items():
        src, *_ = key.split("/", 1)
        sources.setdefault(src, []).append(val)
        ts = val.get("synced_at", 0)
        if ts > latest_ts:
            latest_ts = ts

    _echo_section("Manifest status")
    click.echo(f"  Manifest: {manifest.path}")
    if latest_ts:
        import datetime
        dt = datetime.datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d %H:%M:%S")
        click.echo(f"  Last sync: {dt}")
    click.echo(f"  Total files tracked: {len(data)}")
    click.echo("")
    for src_name, entries in sorted(sources.items()):
        click.echo(f"  {click.style(src_name, bold=True)}: {len(entries)} file(s)")


# ── docsync serve ─────────────────────────────────────────────────────────────

@cli.command()
@click.option("--port", "-p", default=8484, show_default=True, help="Port to serve on.")
@click.pass_context
def serve(ctx: click.Context, port: int) -> None:
    """Start a dev server for the generated site (with admin control panel)."""
    config_path: Path | None = ctx.obj.get("config_path")
    try:
        config, _ = load_and_validate(config_path)
    except ConfigError as exc:
        _echo_err(str(exc))
        sys.exit(1)

    output_dir = config.get("site", {}).get("output_dir", "/tmp/docsync-out")
    output_path = Path(output_dir)
    if not output_path.exists():
        _echo_err(f"Site output directory does not exist: {output_path}")
        _echo_warn("Run `docsync sync` first to generate the site.")
        sys.exit(1)

    from .web import create_app
    app = create_app(config, output_path, config_path)
    click.echo(f"Serving {output_path} at http://localhost:{port}")
    click.echo(f"Admin panel:  http://localhost:{port}/admin")
    click.echo("Press Ctrl+C to stop.")
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except KeyboardInterrupt:
        click.echo("\nServer stopped.")


# ── docsync init ──────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Generate a starter docsync.yaml in ~/.config/docsync/."""
    import shutil

    config_dir = Path("~/.config/docsync").expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    dest = config_dir / "docsync.yaml"

    if dest.exists():
        if not click.confirm(f"{dest} already exists. Overwrite?", default=False):
            click.echo("Aborted.")
            return

    # Find the example config in the package repo
    example = _PKG_DIR.parent / "docsync.yaml.example"
    if example.exists():
        shutil.copy(example, dest)
        _echo_ok(f"Created {dest}")
    else:
        _echo_err(f"Example config not found at {example}")
        sys.exit(1)

    click.echo(f"Edit {dest} then run: docsync check")


# ── docsync add ───────────────────────────────────────────────────────────────

@cli.command("add")
@click.argument("path", required=False)
@click.pass_context
def add_source(ctx: click.Context, path: str | None) -> None:
    """Interactively add a new local source to the config."""
    config_path: Path | None = ctx.obj.get("config_path")
    if config_path is None:
        config_path = Path("~/.config/docsync/docsync.yaml").expanduser()

    if not config_path.exists():
        _echo_err(f"Config not found: {config_path}. Run `docsync init` first.")
        sys.exit(1)

    src_path = Path(path).expanduser().resolve() if path else Path(
        click.prompt("Project path")
    ).expanduser().resolve()

    if not src_path.exists():
        _echo_warn(f"Path does not exist: {src_path} (continuing anyway)")

    name = click.prompt("Source name", default=src_path.name)
    category = click.prompt("Category", default="General")
    includes = click.prompt("Include patterns (comma-separated)", default="**/*.md,README.md")
    backup = click.confirm("Enable backup for this source?", default=True)

    include_list = [p.strip() for p in includes.split(",")]

    import yaml
    with open(config_path) as fh:
        cfg = yaml.safe_load(fh) or {}

    cfg.setdefault("sources", []).append({
        "name": name,
        "type": "local",
        "path": str(src_path),
        "include": include_list,
        "exclude": [".git/**", "__pycache__/**", "node_modules/**"],
        "category": category,
        "backup": {"enabled": backup, "include_all": True, "priority": "normal"},
    })

    with open(config_path, "w") as fh:
        yaml.dump(cfg, fh, default_flow_style=False, allow_unicode=True)

    _echo_ok(f"Added source '{name}' to {config_path}")
    click.echo("Run `docsync check` to validate, then `docsync sync` to collect docs.")


# ── docsync all ───────────────────────────────────────────────────────────────

@cli.command("all")
@click.pass_context
def run_all(ctx: click.Context) -> None:
    """Run documentation sync then backup in sequence."""
    config_path: Path | None = ctx.obj.get("config_path")
    try:
        config, result = load_and_validate(config_path)
    except ConfigError as exc:
        _echo_err(str(exc))
        sys.exit(1)
    if not result.ok():
        for err in result.errors:
            _echo_err(err)
        sys.exit(1)

    from .sync import run_sync
    from .backup.engine import run_backup

    click.echo(click.style("Step 1/2: Documentation sync", bold=True))
    manifest = Manifest()
    sync_stats, _ = run_sync(config, manifest)
    for err in sync_stats.errors:
        _echo_warn(err)
    click.echo(f"  {sync_stats.files_parsed} files parsed, {sync_stats.pages_generated} pages generated")

    click.echo(click.style("\nStep 2/2: Backup", bold=True))
    bk_stats = run_backup(config)
    for err in bk_stats.errors:
        _echo_warn(err)
    click.echo(
        f"  {bk_stats.sources_succeeded}/{bk_stats.sources_attempted} sources backed up, "
        f"{bk_stats.snapshots_pruned} snapshots pruned"
    )

    if sync_stats.ok and bk_stats.ok:
        click.echo(click.style("\nAll done.", fg="green", bold=True))
    else:
        click.echo(click.style("\nCompleted with errors.", fg="yellow"))
        sys.exit(1)


# ── docsync backup (sub-group) ────────────────────────────────────────────────

@cli.group("backup")
@click.pass_context
def backup_group(ctx: click.Context) -> None:
    """Backup management commands."""


def _load_config_for_backup(ctx: click.Context) -> dict:
    config_path: Path | None = ctx.obj.get("config_path")
    try:
        config, _ = load_and_validate(config_path)
        return config
    except ConfigError as exc:
        _echo_err(str(exc))
        sys.exit(1)


@backup_group.command("run")
@click.option("--source", "-s", default=None, help="Back up a single named source.")
@click.option("--full", is_flag=True, default=False, help="Force a full (non-incremental) backup.")
@click.pass_context
def backup_run(ctx: click.Context, source: str | None, full: bool) -> None:
    """Run backup for all (or one) enabled source(s)."""
    from .backup.engine import run_backup

    config = _load_config_for_backup(ctx)
    label = f"source '{source}'" if source else "all sources"
    click.echo(click.style(f"Backing up {label}…", bold=True))
    stats = run_backup(config, source_name=source, force_full=full)

    click.echo(f"  Attempted: {stats.sources_attempted}")
    click.echo(f"  Succeeded: {stats.sources_succeeded}")
    click.echo(f"  Failed:    {stats.sources_failed}")
    click.echo(f"  Pruned:    {stats.snapshots_pruned} snapshots")
    click.echo(f"  Duration:  {stats.duration_seconds:.2f}s")
    for err in stats.errors:
        _echo_err(err)
    if stats.ok:
        click.echo(click.style("  Backup complete.", fg="green", bold=True))
    else:
        sys.exit(1)


@backup_group.command("status")
@click.pass_context
def backup_status_cmd(ctx: click.Context) -> None:
    """Show backup health: last run, sizes, retention."""
    from .backup.report import backup_status

    config = _load_config_for_backup(ctx)
    rows = backup_status(config)
    if not rows:
        click.echo("No backup-enabled sources found or no backups run yet.")
        return

    _echo_section("Backup Status")
    for row in rows:
        status_color = "green" if row["latest_status"] == "ok" else "red"
        click.echo(
            f"  {click.style(row['source_name'], bold=True)}"
            f"  [{click.style(row['latest_status'], fg=status_color)}]"
            f"  {row['snapshot_count']} snapshots"
            f"  {row['total_size_human']}"
        )
        if row["latest_snapshot"]:
            click.echo(
                f"    latest: {row['latest_snapshot']}"
                f"  {row['latest_file_count']} files"
            )


@backup_group.command("list")
@click.argument("source")
@click.pass_context
def backup_list(ctx: click.Context, source: str) -> None:
    """List available snapshots for SOURCE."""
    from .backup.report import source_backup_dir, snapshot_list
    from .utils import human_size

    config = _load_config_for_backup(ctx)
    base_dir_str = config.get("backup", {}).get("base_dir")
    if not base_dir_str:
        _echo_err("backup.base_dir not configured")
        sys.exit(1)

    src_dir = source_backup_dir(Path(base_dir_str).expanduser(), source)
    if not src_dir.exists():
        click.echo(f"No backups found for '{source}'")
        return

    snaps = snapshot_list(src_dir)
    if not snaps:
        click.echo(f"No snapshots for '{source}'")
        return

    click.echo(click.style(f"Snapshots for '{source}':", bold=True))
    for meta in snaps:
        ts = meta.get("timestamp", "?")
        status = meta.get("status", "?")
        files = meta.get("file_count", "?")
        size = human_size(meta.get("size_bytes", 0))
        dur = meta.get("duration_seconds", 0)
        color = "green" if status == "ok" else "red"
        click.echo(
            f"  {ts}  [{click.style(status, fg=color)}]"
            f"  {files} files  {size}  {dur:.1f}s"
        )


@backup_group.command("restore")
@click.argument("source")
@click.argument("snapshot")
@click.option("--dest", default=None, help="Restore to a custom path.")
@click.option("--file", "single_file", default=None, help="Restore a single file from the snapshot.")
@click.pass_context
def backup_restore(
    ctx: click.Context,
    source: str,
    snapshot: str,
    dest: str | None,
    single_file: str | None,
) -> None:
    """Restore a snapshot (or single file) for SOURCE."""
    from .backup.restore import restore_snapshot, restore_file
    from .backup.report import source_backup_dir

    config = _load_config_for_backup(ctx)
    base_dir_str = config.get("backup", {}).get("base_dir")
    if not base_dir_str:
        _echo_err("backup.base_dir not configured")
        sys.exit(1)

    src_dir = source_backup_dir(Path(base_dir_str).expanduser(), source)
    src_config = next((s for s in config.get("sources", []) if s.get("name") == source), None)
    dest_path = Path(dest) if dest else None

    if single_file:
        ok, msg = restore_file(src_dir, snapshot, single_file, dest_path)
    else:
        ok, msg = restore_snapshot(src_dir, snapshot, dest_path, src_config)

    if ok:
        _echo_ok(msg)
    else:
        _echo_err(msg)
        sys.exit(1)


@backup_group.command("prune")
@click.pass_context
def backup_prune(ctx: click.Context) -> None:
    """Manually run retention pruning across all sources."""
    from .backup.retention import apply_retention
    from .backup.report import source_backup_dir
    from .backup.engine import _build_retention

    config = _load_config_for_backup(ctx)
    base_dir_str = config.get("backup", {}).get("base_dir")
    if not base_dir_str:
        _echo_err("backup.base_dir not configured")
        sys.exit(1)

    base_dir = Path(base_dir_str).expanduser()
    retention = _build_retention(config)
    total_pruned = 0

    for src in config.get("sources", []):
        if not src.get("backup", {}).get("enabled", True):
            continue
        src_dir = source_backup_dir(base_dir, src["name"])
        if not src_dir.exists():
            continue
        pruned = apply_retention(src_dir, retention)
        total_pruned += len(pruned)
        if pruned:
            click.echo(f"  {src['name']}: pruned {len(pruned)} snapshot(s)")

    click.echo(f"Total pruned: {total_pruned} snapshot(s)")


@backup_group.command("verify")
@click.argument("source")
@click.pass_context
def backup_verify(ctx: click.Context, source: str) -> None:
    """Verify integrity of the latest snapshot for SOURCE."""
    from .backup.verify import verify_snapshot
    from .backup.snapshot import latest_snapshot
    from .backup.report import source_backup_dir

    config = _load_config_for_backup(ctx)
    base_dir_str = config.get("backup", {}).get("base_dir")
    if not base_dir_str:
        _echo_err("backup.base_dir not configured")
        sys.exit(1)

    src_dir = source_backup_dir(Path(base_dir_str).expanduser(), source)
    snap = latest_snapshot(src_dir)
    if not snap:
        _echo_err(f"No snapshots found for '{source}'")
        sys.exit(1)

    click.echo(f"Verifying {snap.name}…")
    ok, errors = verify_snapshot(snap)
    if ok:
        _echo_ok(f"Snapshot {snap.name} passed integrity check")
    else:
        for err in errors:
            _echo_err(err)
        sys.exit(1)


@backup_group.command("size")
@click.pass_context
def backup_size(ctx: click.Context) -> None:
    """Show total backup storage usage per source."""
    from .backup.report import backup_status
    from .utils import human_size

    config = _load_config_for_backup(ctx)
    rows = backup_status(config)
    if not rows:
        click.echo("No backup data found.")
        return

    total = sum(r["total_size_bytes"] for r in rows)
    max_gb = config.get("backup", {}).get("max_total_size_gb", 0)

    _echo_section("Backup Storage")
    for row in rows:
        bar_width = 20
        pct = (row["total_size_bytes"] / max(total, 1)) * bar_width if total else 0
        bar = "█" * int(pct) + "░" * (bar_width - int(pct))
        click.echo(f"  {row['source_name']:<30} {row['total_size_human']:>8}  {bar}")

    click.echo(f"\n  Total: {human_size(total)}", )
    if max_gb:
        used_pct = (total / (max_gb * 1024**3)) * 100
        color = "red" if used_pct > 90 else "yellow" if used_pct > 75 else "green"
        click.echo(f"  Limit: {max_gb} GB  ({click.style(f'{used_pct:.1f}%', fg=color)} used)")


# ── Private helpers ───────────────────────────────────────────────────────────

def _fresh_result():
    from .config import ValidationResult
    return ValidationResult()


def _print_simple(result, ok_msg: str = "OK") -> None:
    if result.ok() and not result.warnings:
        _echo_ok(ok_msg)
    else:
        for err in result.errors:
            _echo_err(err)
        for warn in result.warnings:
            _echo_warn(warn)


def _print_result_detail(config: dict, result, check_type: str = "paths") -> None:
    local_sources = [s for s in config.get("sources", []) if s.get("type") == "local"]
    if not local_sources:
        _echo_warn("No local sources defined")
        return
    if result.ok() and not result.warnings:
        _echo_ok(f"All {len(local_sources)} local source path(s) exist")
    else:
        for err in result.errors:
            _echo_err(err)
        for warn in result.warnings:
            _echo_warn(warn)


# ── docsync watch ─────────────────────────────────────────────────────────────

@cli.command()
@click.option(
    "--debounce", default=3, show_default=True,
    help="Seconds to wait after last change before syncing.",
)
@click.pass_context
def watch(ctx: click.Context, debounce: int) -> None:
    """Watch local source paths and re-sync on changes (requires inotifywait)."""
    import shutil
    import subprocess

    config_path: Path | None = ctx.obj.get("config_path")
    try:
        config, result = load_and_validate(config_path)
    except ConfigError as exc:
        _echo_err(str(exc))
        sys.exit(1)
    if not result.ok():
        for err in result.errors:
            _echo_err(err)
        sys.exit(1)

    if not shutil.which("inotifywait"):
        _echo_err("inotifywait not found. Install with: sudo apt install inotify-tools")
        sys.exit(1)

    local_paths = [
        s["path"] for s in config.get("sources", [])
        if s.get("type", "local") == "local" and s.get("path")
    ]
    if not local_paths:
        _echo_err("No local sources configured to watch.")
        sys.exit(1)

    from .sync import run_sync

    _echo_ok(f"Watching {len(local_paths)} path(s). Press Ctrl+C to stop.")
    for p in local_paths:
        click.echo(f"   {p}")

    # Run initial sync
    click.echo(click.style("\nInitial sync…", bold=True))
    manifest = Manifest()
    stats, _ = run_sync(config, manifest)
    click.echo(f"  {stats.files_parsed} files parsed, {stats.pages_generated} pages")

    # Monitor with inotifywait -m (monitor mode, continuous output)
    cmd = [
        "inotifywait", "-m", "-r",
        "-e", "modify,create,delete,move",
        "--quiet",
        "--format", "%w%f",
    ] + local_paths

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except OSError as exc:
        _echo_err(f"Failed to start inotifywait: {exc}")
        sys.exit(1)

    pending = False

    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            line = line.strip()
            if not line:
                continue
            if not pending:
                pending = True
                click.echo(click.style(f"\nChange detected: {line}", fg="yellow"))

            # Debounce: wait until no events for `debounce` seconds
            # We can't easily debounce here without threading; instead we
            # batch by flushing whenever stdout is quiet for ~debounce seconds.
            # Simple approach: check if next read times out.
            import select
            rlist, _, _ = select.select([proc.stdout], [], [], float(debounce))
            if not rlist and pending:
                pending = False
                click.echo(click.style("Syncing…", bold=True))
                try:
                    stats, _ = run_sync(config, manifest)
                    click.echo(f"  {stats.files_parsed} parsed, {stats.pages_generated} pages")
                    if stats.errors:
                        for err in stats.errors:
                            _echo_warn(err)
                except Exception as exc:
                    _echo_err(f"Sync error: {exc}")

    except KeyboardInterrupt:
        click.echo("\nStopped.")
    finally:
        proc.terminate()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
