"""Tests for docsync.collector."""

import pytest
from pathlib import Path

from docsync.collector import collect_source, collect_all, _matches_any
from docsync.manifest import Manifest


# ── _matches_any ──────────────────────────────────────────────────────────────

def test_matches_any_glob():
    assert _matches_any("docs/guide.md", ["docs/**/*.md"]) is True
    assert _matches_any("README.md", ["README.md"]) is True
    assert _matches_any("src/main.py", ["**/*.md"]) is False


def test_matches_any_simple_filename():
    # Pattern without '/' should match just the filename
    assert _matches_any("docs/README.md", ["README.md"]) is True
    assert _matches_any("deep/nested/README.md", ["README.md"]) is True


def test_matches_any_no_patterns():
    assert _matches_any("anything.md", []) is False


# ── collect_source (local) ───────────────────────────────────────────────────

@pytest.fixture
def project_tree(tmp_path):
    """Create a minimal project directory tree."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("# Guide\nHello")
    (tmp_path / "docs" / "api.md").write_text("# API\nEndpoints")
    (tmp_path / "README.md").write_text("# Root README")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("# not a doc")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "excluded.md").write_text("should be excluded")
    return tmp_path


def make_manifest(tmp_path):
    return Manifest(tmp_path / "manifest.json")


def test_collects_matching_files(project_tree):
    source = {
        "name": "test-proj",
        "type": "local",
        "path": str(project_tree),
        "include": ["docs/**/*.md", "README.md"],
        "exclude": [],
    }
    manifest = make_manifest(project_tree)
    result = collect_source(source, manifest)

    assert result.ok
    rel_paths = {f.rel_path for f in result.files}
    assert "docs/guide.md" in rel_paths
    assert "docs/api.md" in rel_paths
    assert "README.md" in rel_paths
    assert "src/main.py" not in rel_paths


def test_excludes_patterns(project_tree):
    source = {
        "name": "test-proj",
        "type": "local",
        "path": str(project_tree),
        "include": ["**/*.md"],
        "exclude": ["node_modules/**"],
    }
    manifest = make_manifest(project_tree)
    result = collect_source(source, manifest)

    rel_paths = {f.rel_path for f in result.files}
    assert not any("node_modules" in p for p in rel_paths)


def test_all_files_changed_on_first_run(project_tree):
    source = {
        "name": "test-proj",
        "type": "local",
        "path": str(project_tree),
        "include": ["docs/**/*.md", "README.md"],
        "exclude": [],
    }
    manifest = make_manifest(project_tree)
    result = collect_source(source, manifest)
    assert all(f.changed for f in result.files)


def test_no_files_changed_after_update(project_tree):
    source = {
        "name": "test-proj",
        "type": "local",
        "path": str(project_tree),
        "include": ["docs/**/*.md", "README.md"],
        "exclude": [],
    }
    manifest = make_manifest(project_tree)
    # First run — update manifest
    result1 = collect_source(source, manifest)
    for f in result1.files:
        manifest.update(f.source_name, f.rel_path, f.abs_path)

    # Second run — nothing changed
    result2 = collect_source(source, manifest)
    assert all(not f.changed for f in result2.files)


def test_missing_path_returns_error(tmp_path):
    source = {
        "name": "missing",
        "type": "local",
        "path": str(tmp_path / "does-not-exist"),
        "include": ["**/*.md"],
    }
    manifest = make_manifest(tmp_path)
    result = collect_source(source, manifest)
    assert not result.ok
    assert result.errors


def test_remote_source_fails_gracefully_when_rsync_unreachable(tmp_path):
    """Remote source returns an error result (not exception) when host is unreachable."""
    source = {
        "name": "remote-proj",
        "type": "remote",
        "host": "192.0.2.1",  # TEST-NET, guaranteed unreachable
        "user": "pi",
        "path": "/opt/project",
        "include": ["**/*.md"],
    }
    manifest = make_manifest(tmp_path)
    result = collect_source(source, manifest)
    # Should return a result with errors, not raise
    assert not result.ok
    assert result.errors


def test_collect_all_includes_both_local_and_remote(tmp_path):
    """collect_all processes both local and remote sources (remote may error)."""
    (tmp_path / "README.md").write_text("hello")
    config = {
        "sources": [
            {
                "name": "local-src",
                "type": "local",
                "path": str(tmp_path),
                "include": ["README.md"],
            },
            {
                "name": "remote-src",
                "type": "remote",
                "host": "192.0.2.1",  # unreachable
                "user": "pi",
                "path": "/opt/x",
                "include": ["**/*.md"],
            },
        ]
    }
    manifest = make_manifest(tmp_path)
    results = collect_all(config, manifest)
    assert len(results) == 2
    assert results[0].source_name == "local-src"
    assert results[0].ok
    assert results[1].source_name == "remote-src"
    assert not results[1].ok  # failed to connect


def test_collect_all_single_source(tmp_path):
    (tmp_path / "README.md").write_text("hello")
    config = {
        "sources": [
            {"name": "A", "type": "local", "path": str(tmp_path), "include": ["README.md"]},
            {"name": "B", "type": "local", "path": str(tmp_path), "include": ["README.md"]},
        ]
    }
    manifest = make_manifest(tmp_path)
    results = collect_all(config, manifest, source_name="A")
    assert len(results) == 1
    assert results[0].source_name == "A"


def test_collect_all_unknown_source_raises(tmp_path):
    config = {"sources": [
        {"name": "A", "type": "local", "path": str(tmp_path), "include": ["README.md"]},
    ]}
    manifest = make_manifest(tmp_path)
    with pytest.raises(ValueError, match="No source named"):
        collect_all(config, manifest, source_name="MISSING")
