"""Tests for docsync.config — loader, schema validation, and runtime checks."""

import os
import textwrap
from pathlib import Path

import pytest
import yaml

from docsync.config import (
    ConfigError,
    ValidationResult,
    check_backup_base_dir,
    check_local_paths,
    load_config,
    load_and_validate,
    validate_config,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def write_yaml(tmp_path: Path, data: dict | str) -> Path:
    """Write a YAML config to a temp file and return the path."""
    p = tmp_path / "docsync.yaml"
    if isinstance(data, str):
        p.write_text(textwrap.dedent(data))
    else:
        p.write_text(yaml.dump(data))
    return p


MINIMAL_CONFIG = {
    "site": {
        "title": "Test Wiki",
        "output_dir": "/tmp/docsync-out",
        "base_url": "http://localhost:8484",
    },
    "sources": [],
}


# ── load_config ───────────────────────────────────────────────────────────────

class TestLoadConfig:
    def test_loads_valid_yaml(self, tmp_path):
        p = write_yaml(tmp_path, MINIMAL_CONFIG)
        config = load_config(p)
        assert isinstance(config, dict)
        assert "site" in config

    def test_raises_on_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_raises_on_invalid_yaml(self, tmp_path):
        p = tmp_path / "docsync.yaml"
        p.write_text("key: [\nunclosed bracket")
        with pytest.raises(ConfigError, match="YAML parse error"):
            load_config(p)

    def test_raises_on_non_mapping(self, tmp_path):
        p = tmp_path / "docsync.yaml"
        p.write_text("- just\n- a\n- list\n")
        with pytest.raises(ConfigError, match="must be a YAML mapping"):
            load_config(p)


# ── validate_config ───────────────────────────────────────────────────────────

class TestValidateConfig:
    def test_minimal_valid_config(self):
        result = validate_config(MINIMAL_CONFIG)
        assert result.ok()

    def test_missing_site_output_dir(self):
        config = {"site": {"title": "T", "base_url": "http://x"}, "sources": []}
        result = validate_config(config)
        assert not result.ok()
        assert any("output_dir" in e for e in result.errors)

    def test_invalid_backup_strategy(self):
        config = {**MINIMAL_CONFIG, "backup": {"enabled": True, "base_dir": "/tmp/bak", "strategy": "magic"}}
        result = validate_config(config)
        assert not result.ok()
        assert any("strategy" in e for e in result.errors)

    def test_invalid_backup_compression(self):
        config = {**MINIMAL_CONFIG, "backup": {"enabled": True, "base_dir": "/tmp/bak", "compression": "lz4"}}
        result = validate_config(config)
        assert not result.ok()
        assert any("compression" in e for e in result.errors)

    def test_invalid_cron_expression(self):
        config = {**MINIMAL_CONFIG, "sync": {"schedule": "not-a-cron"}}
        result = validate_config(config)
        assert not result.ok()
        assert any("cron" in e for e in result.errors)

    def test_valid_cron_expression(self):
        config = {**MINIMAL_CONFIG, "sync": {"schedule": "0 */4 * * *"}}
        result = validate_config(config)
        assert result.ok()

    def test_source_missing_type(self):
        config = {**MINIMAL_CONFIG, "sources": [{"name": "X", "path": "/tmp"}]}
        result = validate_config(config)
        assert not result.ok()
        assert any("type" in e for e in result.errors)

    def test_source_invalid_type(self):
        config = {**MINIMAL_CONFIG, "sources": [{"name": "X", "path": "/tmp", "type": "ftp"}]}
        result = validate_config(config)
        assert not result.ok()

    def test_remote_source_missing_host(self):
        config = {**MINIMAL_CONFIG, "sources": [
            {"name": "X", "type": "remote", "path": "/opt/x", "user": "pi"}
        ]}
        result = validate_config(config)
        assert not result.ok()
        assert any("host" in e for e in result.errors)

    def test_source_backup_invalid_priority(self):
        config = {**MINIMAL_CONFIG, "sources": [
            {
                "name": "X", "type": "local", "path": "/tmp",
                "backup": {"priority": "ultra"},
            }
        ]}
        result = validate_config(config)
        assert not result.ok()
        assert any("priority" in e for e in result.errors)

    def test_include_db_without_db_block(self):
        config = {**MINIMAL_CONFIG, "sources": [
            {
                "name": "X", "type": "local", "path": "/tmp",
                "backup": {"include_db": True},
            }
        ]}
        result = validate_config(config)
        assert not result.ok()
        assert any("include_db" in e for e in result.errors)

    def test_no_sources_warning(self):
        result = validate_config({"site": MINIMAL_CONFIG["site"]})
        assert result.ok()  # warning, not error
        assert any("sources" in w for w in result.warnings)

    def test_overlapping_local_sources(self, tmp_path):
        config = {**MINIMAL_CONFIG, "sources": [
            {"name": "A", "type": "local", "path": str(tmp_path)},
            {"name": "B", "type": "local", "path": str(tmp_path)},
        ]}
        result = validate_config(config)
        assert any("Overlapping" in w for w in result.warnings)


# ── check_local_paths ─────────────────────────────────────────────────────────

class TestCheckLocalPaths:
    def test_existing_path_passes(self, tmp_path):
        config = {**MINIMAL_CONFIG, "sources": [
            {"name": "X", "type": "local", "path": str(tmp_path)},
        ]}
        result = ValidationResult()
        check_local_paths(config, result)
        assert result.ok()

    def test_missing_path_errors(self, tmp_path):
        config = {**MINIMAL_CONFIG, "sources": [
            {"name": "X", "type": "local", "path": str(tmp_path / "does-not-exist")},
        ]}
        result = ValidationResult()
        check_local_paths(config, result)
        assert not result.ok()
        assert any("does not exist" in e for e in result.errors)

    def test_file_not_dir_errors(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        config = {**MINIMAL_CONFIG, "sources": [
            {"name": "X", "type": "local", "path": str(f)},
        ]}
        result = ValidationResult()
        check_local_paths(config, result)
        assert not result.ok()
        assert any("not a directory" in e for e in result.errors)

    def test_remote_sources_skipped(self, tmp_path):
        config = {**MINIMAL_CONFIG, "sources": [
            {"name": "R", "type": "remote", "path": "/nonexistent/path"},
        ]}
        result = ValidationResult()
        check_local_paths(config, result)
        assert result.ok()


# ── check_backup_base_dir ─────────────────────────────────────────────────────

class TestCheckBackupBaseDir:
    def test_existing_writable_dir(self, tmp_path):
        config = {"backup": {"enabled": True, "base_dir": str(tmp_path)}}
        result = ValidationResult()
        check_backup_base_dir(config, result)
        assert result.ok()

    def test_nonexistent_dir_warns(self, tmp_path):
        config = {"backup": {"enabled": True, "base_dir": str(tmp_path / "new-backup-dir")}}
        result = ValidationResult()
        check_backup_base_dir(config, result)
        assert result.ok()  # warning, not error
        assert any("created" in w for w in result.warnings)

    def test_disabled_backup_skipped(self, tmp_path):
        config = {"backup": {"enabled": False, "base_dir": "/nonexistent/path"}}
        result = ValidationResult()
        check_backup_base_dir(config, result)
        assert result.ok()

    def test_unwritable_dir_errors(self, tmp_path):
        protected = tmp_path / "protected"
        protected.mkdir()
        os.chmod(protected, 0o444)
        try:
            config = {"backup": {"enabled": True, "base_dir": str(protected)}}
            result = ValidationResult()
            check_backup_base_dir(config, result)
            if os.getuid() != 0:  # root ignores permissions
                assert not result.ok()
                assert any("not writable" in e for e in result.errors)
        finally:
            os.chmod(protected, 0o755)
