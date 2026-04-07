"""Tests for docsync.generator."""

from pathlib import Path

import pytest

from docsync.generator import SiteGenerator, _slugify, generate_site
from docsync.parser import ParsedDoc, TocEntry


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_doc(
    source_name="my-project",
    rel_path="guide.md",
    title="My Guide",
    description="A guide",
    tags=None,
    order=9999,
    html_body="<p>Hello</p>",
    toc=None,
) -> ParsedDoc:
    return ParsedDoc(
        source_name=source_name,
        rel_path=rel_path,
        abs_path=Path("/fake/guide.md"),
        title=title,
        description=description,
        tags=tags or [],
        order=order,
        html_body=html_body,
        toc=toc or [TocEntry(level=2, text="Intro", slug="intro")],
    )


MINIMAL_CONFIG = {
    "site": {
        "title": "Test Wiki",
        "output_dir": "",  # will be set per-test
        "base_url": "http://localhost:8484",
    },
    "sources": [
        {
            "name": "my-project",
            "type": "local",
            "path": "/fake/project",
            "category": "Projects",
            "backup": {"enabled": True},
        }
    ],
}


def make_config(tmp_path: Path) -> dict:
    cfg = {k: v for k, v in MINIMAL_CONFIG.items()}
    cfg["site"] = {**MINIMAL_CONFIG["site"], "output_dir": str(tmp_path / "out")}
    return cfg


# ── _slugify ──────────────────────────────────────────────────────────────────

def test_slugify():
    assert _slugify("My Project") == "my-project"
    assert _slugify("CoreAI Suite!") == "coreai-suite"
    assert _slugify("  leading spaces  ") == "leading-spaces"


def test_slugify_truncates_long_names():
    long_name = "a" * 250
    slug = _slugify(long_name, truncate=True)
    assert len(slug) <= 200
    assert slug.startswith("aaaaa")
    assert slug.endswith("-aaa")


# ── SiteGenerator ─────────────────────────────────────────────────────────────

class TestSiteGenerator:
    def test_generates_index(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc()]
        gen = SiteGenerator(config, docs)
        gen.generate()

        index = tmp_path / "out" / "index.html"
        assert index.exists()
        content = index.read_text()
        assert "Test Wiki" in content
        assert "my-project" in content.lower() or "My" in content

    def test_generates_project_page(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc()]
        gen = SiteGenerator(config, docs)
        gen.generate()

        project = tmp_path / "out" / "projects" / "my-project" / "index.html"
        assert project.exists()
        content = project.read_text()
        assert "my-project" in content.lower() or "My Guide" in content

    def test_generates_doc_page(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc()]
        gen = SiteGenerator(config, docs)
        gen.generate()

        doc_page = tmp_path / "out" / "projects" / "my-project" / "my-guide.html"
        assert doc_page.exists()
        content = doc_page.read_text()
        assert "My Guide" in content
        assert "Hello" in content  # html_body content

    def test_generates_static_pages(self, tmp_path):
        config = make_config(tmp_path)
        gen = SiteGenerator(config, [])
        gen.generate()

        for page in ("search.html", "updates.html", "backups.html"):
            assert (tmp_path / "out" / page).exists()

    def test_copies_assets(self, tmp_path):
        config = make_config(tmp_path)
        gen = SiteGenerator(config, [])
        gen.generate()

        assert (tmp_path / "out" / "assets" / "style.css").exists()
        assert (tmp_path / "out" / "assets" / "search.js").exists()

    def test_returns_page_count(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc(title="Doc A"), make_doc(title="Doc B", rel_path="b.md")]
        gen = SiteGenerator(config, docs)
        pages = gen.generate()
        # index(1) + search+updates(2) + backups.html(1) + 1 backup source page
        # + 1 project + 2 docs = 8
        assert pages == 8

    def test_prev_next_navigation(self, tmp_path):
        config = make_config(tmp_path)
        docs = [
            make_doc(title="Alpha", rel_path="alpha.md", order=1),
            make_doc(title="Beta", rel_path="beta.md", order=2),
            make_doc(title="Gamma", rel_path="gamma.md", order=3),
        ]
        gen = SiteGenerator(config, docs)
        gen.generate()

        beta_page = tmp_path / "out" / "projects" / "my-project" / "beta.html"
        content = beta_page.read_text()
        assert "Alpha" in content  # prev
        assert "Gamma" in content  # next

    def test_toc_rendered_in_doc(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc(
            toc=[TocEntry(level=2, text="Setup", slug="setup"),
                 TocEntry(level=3, text="Details", slug="details")]
        )]
        gen = SiteGenerator(config, docs)
        gen.generate()

        doc_page = tmp_path / "out" / "projects" / "my-project" / "my-guide.html"
        content = doc_page.read_text()
        assert "#setup" in content
        assert "#details" in content

    def test_html_not_escaped_in_body(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc(html_body="<h2>Real Heading</h2><p>Real paragraph.</p>")]
        gen = SiteGenerator(config, docs)
        gen.generate()

        doc_page = tmp_path / "out" / "projects" / "my-project" / "my-guide.html"
        content = doc_page.read_text()
        assert "<h2>Real Heading</h2>" in content
        assert "&lt;h2&gt;" not in content

    def test_empty_sources_generates_site(self, tmp_path):
        config = make_config(tmp_path)
        config["sources"] = []
        gen = SiteGenerator(config, [])
        pages = gen.generate()
        assert pages >= 1  # at least index.html

    def test_multiple_categories(self, tmp_path):
        config = {**make_config(tmp_path), "sources": [
            {"name": "Alpha", "type": "local", "path": "/p", "category": "Tools"},
            {"name": "Beta", "type": "local", "path": "/q", "category": "Products"},
        ]}
        gen = SiteGenerator(config, [])
        gen.generate()

        assert (tmp_path / "out" / "tools" / "alpha" / "index.html").exists()
        assert (tmp_path / "out" / "products" / "beta" / "index.html").exists()

    def test_breadcrumbs_in_doc(self, tmp_path):
        config = make_config(tmp_path)
        docs = [make_doc()]
        gen = SiteGenerator(config, docs)
        gen.generate()

        doc_page = tmp_path / "out" / "projects" / "my-project" / "my-guide.html"
        content = doc_page.read_text()
        assert "Dashboard" in content
        assert "Projects" in content


# ── generate_site convenience function ────────────────────────────────────────

def test_generate_site_function(tmp_path):
    config = make_config(tmp_path)
    docs = [make_doc()]
    count = generate_site(config, docs)
    assert count > 0
    assert (tmp_path / "out" / "index.html").exists()
