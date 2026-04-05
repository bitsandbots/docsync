"""Tests for docsync.manifest."""

import time
from pathlib import Path

from docsync.manifest import Manifest


def test_new_file_is_changed(tmp_path):
    m = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "README.md"
    f.write_text("hello")
    assert m.is_changed("src", "README.md", f) is True


def test_unchanged_file_is_not_changed(tmp_path):
    m = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "README.md"
    f.write_text("hello")
    m.update("src", "README.md", f)
    assert m.is_changed("src", "README.md", f) is False


def test_modified_file_is_changed(tmp_path):
    m = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "README.md"
    f.write_text("v1")
    m.update("src", "README.md", f)
    f.write_text("v2 — different content")
    assert m.is_changed("src", "README.md", f) is True


def test_save_and_reload(tmp_path):
    p = tmp_path / "manifest.json"
    m1 = Manifest(p)
    f = tmp_path / "doc.md"
    f.write_text("content")
    m1.update("proj", "doc.md", f)
    m1.save()

    m2 = Manifest(p)
    assert m2.is_changed("proj", "doc.md", f) is False


def test_remove_source_clears_entries(tmp_path):
    m = Manifest(tmp_path / "manifest.json")
    f = tmp_path / "doc.md"
    f.write_text("x")
    m.update("proj", "doc.md", f)
    assert m.source_keys("proj") == ["doc.md"]
    m.remove_source("proj")
    assert m.source_keys("proj") == []


def test_source_keys_isolation(tmp_path):
    m = Manifest(tmp_path / "manifest.json")
    fa = tmp_path / "a.md"
    fb = tmp_path / "b.md"
    fa.write_text("a")
    fb.write_text("b")
    m.update("alpha", "a.md", fa)
    m.update("beta", "b.md", fb)
    assert m.source_keys("alpha") == ["a.md"]
    assert m.source_keys("beta") == ["b.md"]
