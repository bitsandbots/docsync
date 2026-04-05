"""Tests for docsync.parser."""

from pathlib import Path
import pytest

from docsync.parser import (
    TocEntry,
    _extract_front_matter,
    _slugify,
    parse_file,
    parse_files,
)
from docsync.collector import CollectedFile


# ── _slugify ──────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert _slugify("Hello World") == "hello-world"


def test_slugify_strips_special():
    assert _slugify("API Reference!") == "api-reference"


def test_slugify_collapses_spaces():
    assert _slugify("  Multiple   Spaces  ") == "multiple-spaces"


def test_slugify_handles_hyphens():
    assert _slugify("already-slugged") == "already-slugged"


# ── _extract_front_matter ─────────────────────────────────────────────────────

def test_extract_front_matter_basic():
    src = "---\ntitle: My Doc\ntags: [a, b]\n---\n# Body\n"
    meta, body = _extract_front_matter(src)
    assert meta["title"] == "My Doc"
    assert meta["tags"] == ["a", "b"]
    assert body.startswith("# Body")


def test_extract_no_front_matter():
    src = "# Just content\nNo front matter here."
    meta, body = _extract_front_matter(src)
    assert meta == {}
    assert body == src


def test_extract_invalid_yaml_returns_empty():
    src = "---\n: invalid: yaml: [\n---\n# Body\n"
    meta, body = _extract_front_matter(src)
    assert meta == {}


# ── parse_file ────────────────────────────────────────────────────────────────

def test_parse_file_basic(tmp_path):
    f = tmp_path / "guide.md"
    f.write_text("---\ntitle: My Guide\ndescription: A guide.\ntags: [howto]\norder: 2\n---\n\n# Intro\n\nHello world.\n\n## Details\n\nMore info.\n")
    doc = parse_file(f, "test-src", "guide.md")

    assert doc is not None
    assert doc.title == "My Guide"
    assert doc.description == "A guide."
    assert doc.tags == ["howto"]
    assert doc.order == 2
    assert "<h1" in doc.html_body
    assert "<h2" in doc.html_body
    assert len(doc.toc) == 2


def test_parse_file_title_from_h1(tmp_path):
    f = tmp_path / "readme.md"
    f.write_text("# My Project\n\nSome content.\n")
    doc = parse_file(f, "src", "readme.md")
    assert doc.title == "My Project"


def test_parse_file_title_from_filename(tmp_path):
    f = tmp_path / "getting-started.md"
    f.write_text("No heading at all.\n")
    doc = parse_file(f, "src", "getting-started.md")
    assert doc.title == "Getting Started"


def test_parse_file_toc_entries(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("# Title\n\n## Section One\n\n### Sub\n\n## Section Two\n")
    doc = parse_file(f, "src", "doc.md")
    levels = [e.level for e in doc.toc]
    assert levels == [1, 2, 3, 2]
    assert doc.toc[1].slug == "section-one"


def test_parse_file_heading_ids_injected(tmp_path):
    f = tmp_path / "doc.md"
    f.write_text("## Installation\n\nSteps here.\n")
    doc = parse_file(f, "src", "doc.md")
    assert 'id="installation"' in doc.html_body


def test_parse_file_missing_returns_none(tmp_path):
    result = parse_file(tmp_path / "nonexistent.md", "src", "nonexistent.md")
    assert result is None


def test_parse_file_xss_sanitized(tmp_path):
    """Raw HTML should not be passed through (html: False in renderer)."""
    f = tmp_path / "doc.md"
    f.write_text("Normal text.\n\n<script>alert('xss')</script>\n")
    doc = parse_file(f, "src", "doc.md")
    assert "<script>" not in doc.html_body


# ── parse_files ───────────────────────────────────────────────────────────────

def make_cf(abs_path: Path, changed: bool = True) -> CollectedFile:
    return CollectedFile(
        source_name="src",
        abs_path=abs_path,
        rel_path=abs_path.name,
        changed=changed,
    )


def test_parse_files_all(tmp_path):
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("# A\n")
    f2.write_text("# B\n")
    docs = parse_files([make_cf(f1), make_cf(f2)])
    assert len(docs) == 2


def test_parse_files_changed_only(tmp_path):
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("# A\n")
    f2.write_text("# B\n")
    docs = parse_files([make_cf(f1, changed=True), make_cf(f2, changed=False)], changed_only=True)
    assert len(docs) == 1
    assert docs[0].title == "A"
