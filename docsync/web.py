"""Flask-based dev server with admin control panel for DocSync."""

import subprocess
import sys
from pathlib import Path
from subprocess import PIPE, STDOUT

from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from flask.helpers import stream_with_context


def create_app(config: dict, output_dir: Path, config_path: Path | None = None) -> Flask:
    """Create and return the Flask application.

    Args:
        config: Loaded docsync configuration dict.
        output_dir: Path to the generated static site output directory.
        config_path: Optional explicit config file path (forwarded to subprocesses).
    """
    app = Flask(__name__, template_folder="templates")
    app.config["OUTPUT_DIR"] = str(output_dir)
    app.config["DOCSYNC_CONFIG"] = str(config_path) if config_path else None
    
    # Store initial state in app.config (reloaded via /api/reload)
    app.config["SOURCES"] = [s["name"] for s in config.get("sources", [])]
    app.config["SITE_TITLE"] = config.get("site", {}).get("title", "DocSync")
    app.config["BACKUP_BASE_DIR"] = config.get("backup", {}).get("base_dir")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _base_cmd() -> list[str]:
        """Return base docsync command, injecting --config if set."""
        cmd = [sys.executable, "-m", "docsync.cli"]
        cfg = app.config["DOCSYNC_CONFIG"]
        if cfg:
            cmd += ["--config", cfg]
        return cmd

    def _stream(args: list[str]) -> Response:
        """Run *args* as a subprocess and stream stdout+stderr as SSE."""
        def generate():
            proc = subprocess.Popen(args, stdout=PIPE, stderr=STDOUT, text=True)
            for line in proc.stdout:
                yield f"data: {line.rstrip()}\n\n"
            proc.wait()
            yield f"data: [exit:{proc.returncode}]\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Static site ───────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(app.config["OUTPUT_DIR"], "index.html")

    @app.route("/<path:filename>")
    def static_site(filename):
        return send_from_directory(app.config["OUTPUT_DIR"], filename)

    # ── Admin panel ───────────────────────────────────────────────────────────

    @app.route("/admin")
    def admin():
        return render_template(
            "admin.html",
            sources=app.config["SOURCES"],
            site_title=app.config["SITE_TITLE"],
        )

    # ── API: sync ─────────────────────────────────────────────────────────────

    @app.route("/api/sync", methods=["POST"])
    def api_sync():
        data = request.get_json(silent=True) or {}
        args = _base_cmd() + ["sync"]
        src = data.get("source")
        if src:
            args += ["--source", src]
        return _stream(args)

    # ── API: backup run ───────────────────────────────────────────────────────

    @app.route("/api/backup/run", methods=["POST"])
    def api_backup_run():
        data = request.get_json(silent=True) or {}
        args = _base_cmd() + ["backup", "run"]
        src = data.get("source")
        if src:
            args += ["--source", src]
        if data.get("full"):
            args.append("--full")
        return _stream(args)

    # ── API: backup restore ───────────────────────────────────────────────────

    @app.route("/api/backup/restore", methods=["POST"])
    def api_backup_restore():
        data = request.get_json(silent=True) or {}
        source = data.get("source", "")
        snapshot = data.get("snapshot", "")
        if not source or not snapshot:
            return jsonify({"error": "source and snapshot are required"}), 400
        args = _base_cmd() + ["backup", "restore", source, snapshot]
        dest = data.get("dest")
        if dest:
            args += ["--dest", dest]
        return _stream(args)

    # ── API: check ────────────────────────────────────────────────────────────

    @app.route("/api/check")
    def api_check():
        args = _base_cmd() + ["check"]
        return _stream(args)

    # ── API: status (JSON) ────────────────────────────────────────────────────

    @app.route("/api/status")
    def api_status():
        from .manifest import Manifest
        import datetime

        manifest = Manifest()
        data = manifest._data  # noqa: SLF001
        if not data:
            return jsonify({"last_sync": None, "total_files": 0, "sources": {}})

        latest_ts = 0
        src_counts: dict[str, int] = {}
        for key in data:
            src, *_ = key.split("/", 1)
            src_counts[src] = src_counts.get(src, 0) + 1
            ts = data[key].get("synced_at", 0)
            if ts > latest_ts:
                latest_ts = ts

        last_sync = (
            datetime.datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d %H:%M:%S")
            if latest_ts
            else None
        )
        return jsonify({
            "last_sync": last_sync,
            "total_files": len(data),
            "sources": src_counts,
        })

    # ── API: snapshot list (JSON) ─────────────────────────────────────────────

    @app.route("/api/backup/snapshots")
    def api_backup_snapshots():
        source = request.args.get("source", "")
        base_dir_str = app.config["BACKUP_BASE_DIR"]
        if not source or not base_dir_str:
            return jsonify([])

        from .backup.report import source_backup_dir, snapshot_list

        src_dir = source_backup_dir(Path(base_dir_str).expanduser(), source)
        if not src_dir.exists():
            return jsonify([])

        snaps = snapshot_list(src_dir)
        return jsonify([
            {
                "timestamp": s.get("timestamp", ""),
                "ts_human": s.get("ts_human", ""),
                "status": s.get("status", "unknown"),
                "file_count": s.get("file_count", 0),
                "size_human": s.get("size_human", "—"),
            }
            for s in snaps
        ])

    # ── Config editor ─────────────────────────────────────────────────────────

    def _resolved_config_path() -> Path:
        """Return the absolute config file path, resolving the default if unset."""
        cfg = app.config["DOCSYNC_CONFIG"]
        if cfg:
            return Path(cfg).expanduser().resolve()
        return Path("~/.config/docsync/docsync.yaml").expanduser()

    @app.route("/admin/config")
    def admin_config():
        return render_template("config.html", site_title=app.config["SITE_TITLE"])

    @app.route("/api/config")
    def api_config_get():
        import yaml
        cfg_path = _resolved_config_path()
        try:
            raw = cfg_path.read_text()
            parsed = yaml.safe_load(raw) or {}
        except FileNotFoundError:
            raw = ""
            parsed = {}
        except yaml.YAMLError as exc:
            return jsonify({"error": f"YAML parse error: {exc}"}), 500
        except OSError as exc:
            return jsonify({"error": f"Cannot read config: {exc}"}), 500
        return jsonify({"raw_yaml": raw, "config": parsed, "config_path": str(cfg_path)})

    @app.route("/api/config/raw", methods=["POST"])
    def api_config_raw():
        import yaml
        raw = request.get_data(as_text=True)
        try:
            yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            return jsonify({"error": f"YAML parse error: {exc}"}), 400

        cfg_path = _resolved_config_path()

        def generate():
            try:
                tmp = cfg_path.with_suffix(".tmp")
                tmp.write_text(raw)
                tmp.rename(cfg_path)
                yield "data: Config saved.\n\n"
            except OSError as exc:
                yield f"data: Error saving: {exc}\n\n"
                yield "data: [exit:1]\n\n"
                return
            yield from _stream_gen(_base_cmd() + ["check"])

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.route("/api/config/structured", methods=["POST"])
    def api_config_structured():
        import yaml
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid JSON"}), 400

        _clean_dict(data)
        cfg_path = _resolved_config_path()

        def generate():
            try:
                raw = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
                tmp = cfg_path.with_suffix(".tmp")
                tmp.write_text(raw)
                tmp.rename(cfg_path)
                yield "data: Config saved.\n\n"
            except (yaml.YAMLError, OSError) as exc:
                yield f"data: Error saving: {exc}\n\n"
                yield "data: [exit:1]\n\n"
                return
            yield from _stream_gen(_base_cmd() + ["check"])

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── API: reload config ────────────────────────────────────────────────────

    @app.route("/api/reload", methods=["POST"])
    def api_reload():
        """Re-read config from disk and refresh in-memory state."""
        import yaml

        cfg_path = _resolved_config_path()
        try:
            new_cfg = yaml.safe_load(cfg_path.read_text()) or {}
        except FileNotFoundError:
            return jsonify({"error": f"Config file not found: {cfg_path}"}), 404
        except yaml.YAMLError as exc:
            return jsonify({"error": f"YAML parse error: {exc}"}), 400
        except OSError as exc:
            return jsonify({"error": str(exc)}), 500

        app.config["SOURCES"] = [s["name"] for s in new_cfg.get("sources", [])]
        app.config["SITE_TITLE"] = new_cfg.get("site", {}).get("title", "DocSync")
        app.config["BACKUP_BASE_DIR"] = new_cfg.get("backup", {}).get("base_dir")

        return jsonify({
            "ok": True,
            "sources": app.config["SOURCES"],
            "site_title": app.config["SITE_TITLE"],
        })

    return app


def _stream_gen(args: list[str]):
    """Generator that yields SSE lines from a subprocess."""
    proc = subprocess.Popen(args, stdout=PIPE, stderr=STDOUT, text=True)
    for line in proc.stdout:
        yield f"data: {line.rstrip()}\n\n"
    proc.wait()
    yield f"data: [exit:{proc.returncode}]\n\n"


def _clean_dict(d: dict) -> None:
    """Recursively remove empty-string and None values from a config dict.

    Retention numeric fields are coerced to int. Source include/exclude
    lists that arrived as newline-delimited strings are split into lists.
    """
    for key in list(d.keys()):
        val = d[key]
        if val == "" or val is None:
            del d[key]
        elif isinstance(val, dict):
            _clean_dict(val)
            if not val:
                del d[key]
        elif isinstance(val, list):
            d[key] = [v for v in val if v not in ("", None)]
    # Coerce retention integers
    if "retention" in d and isinstance(d["retention"], dict):
        for field in ("daily", "weekly", "monthly"):
            if field in d["retention"]:
                try:
                    d["retention"][field] = int(d["retention"][field])
                except (ValueError, TypeError):
                    pass
    # Coerce port on sources
    if "port" in d:
        try:
            d["port"] = int(d["port"])
        except (ValueError, TypeError):
            pass
