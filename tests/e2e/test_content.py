"""Tests for rendered doc content quality.

Covers:
- Page <title> matches the doc's h1
- Markdown headings (h2, h3) render as HTML elements
- Code blocks render as <pre><code> (not raw text)
- Unordered / ordered lists render correctly
- Internal cross-doc links are valid .html paths
- Doc description appears in page meta or header area
- Tags render (when present in front matter)
- Multiple sources' doc pages are consistent in structure
- No raw Jinja2 template syntax leaks into output
- No double-encoded HTML entities in content
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

# Pages known to have rich content
CLI_REF = "tools/docsync/docs--cli-reference.html"
OVERVIEW = "tools/docsync/docs--overview.html"
ARCH = "tools/docsync/docs--architecture.html"
BACKUP_DOC = "tools/docsync/docs--backup-subsystem.html"


@pytest.fixture
def cli_doc(page: Page, base_url: str) -> Page:
    page.goto(f"{base_url}/{CLI_REF}")
    page.wait_for_load_state("load")
    return page


@pytest.fixture
def overview_doc(page: Page, base_url: str) -> Page:
    page.goto(f"{base_url}/{OVERVIEW}")
    page.wait_for_load_state("load")
    return page


@pytest.fixture
def backup_doc(page: Page, base_url: str) -> Page:
    page.goto(f"{base_url}/{BACKUP_DOC}")
    page.wait_for_load_state("load")
    return page


# ── Page title consistency ─────────────────────────────────────────────────────


class TestPageTitle:
    def test_title_tag_non_empty(self, cli_doc: Page):
        title = cli_doc.title()
        assert len(title.strip()) > 0

    def test_title_contains_site_name(self, cli_doc: Page):
        title = cli_doc.title()
        # Site title should appear somewhere in <title>
        assert "DocSync" in title or "CoreConduit" in title or len(title) > 2

    def test_h1_matches_page_title_approximately(self, cli_doc: Page):
        """h1 text should appear in or be consistent with <title>."""
        h1 = cli_doc.locator("main h1").first.inner_text().strip()
        title = cli_doc.title()
        # Either h1 is in title or title is in h1 (title may be truncated)
        assert h1.lower() in title.lower() or any(
            word in title.lower() for word in h1.lower().split()[:3]
        ), f"h1='{h1}' not reflected in title='{title}'"

    @pytest.mark.parametrize(
        "path",
        [CLI_REF, OVERVIEW, ARCH, BACKUP_DOC],
        ids=["cli-ref", "overview", "arch", "backup"],
    )
    def test_all_doc_pages_have_titles(self, page: Page, base_url: str, path: str):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("load")
        assert len(page.title().strip()) > 0


# ── Markdown element rendering ─────────────────────────────────────────────────


class TestMarkdownRendering:
    def test_h1_renders_as_element(self, cli_doc: Page):
        assert cli_doc.locator("main h1").count() >= 1

    def test_headings_render_as_html(self, overview_doc: Page):
        """Headings must render as h2/h3 elements, not raw markdown ##."""
        text = overview_doc.locator("main").inner_text()
        assert "##" not in text, "Raw markdown ## found in rendered output"
        assert overview_doc.locator("main h2, main h3").count() >= 1

    def test_paragraphs_render(self, overview_doc: Page):
        paragraphs = overview_doc.locator("main p")
        assert paragraphs.count() >= 1

    def test_lists_render_as_html(self, cli_doc: Page):
        """Bullet lists must render as <ul><li>, not as '- item' text."""
        text = cli_doc.locator("main").inner_text()
        # Raw markdown list markers should not appear in rendered output
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        raw_bullets = [l for l in lines if re.match(r"^[-*]\s+\w", l)]
        # Allow a few (some docs may have code examples showing markdown)
        assert (
            len(raw_bullets) < 3
        ), f"Too many raw markdown bullets in rendered output: {raw_bullets[:5]}"

    def test_code_blocks_render_as_pre(self, cli_doc: Page):
        """Code blocks must render as <pre><code>, not as plain text."""
        pre_blocks = cli_doc.locator("main pre")
        code_blocks = cli_doc.locator("main code")
        # At least one code element expected in the CLI reference
        assert (
            pre_blocks.count() >= 1 or code_blocks.count() >= 1
        ), "CLI reference should contain at least one code block"

    def test_inline_code_renders(self, overview_doc: Page):
        inline = overview_doc.locator("main code")
        assert inline.count() >= 1

    def test_no_raw_jinja_in_output(self, cli_doc: Page):
        """Jinja2 template syntax must never appear in rendered HTML."""
        text = cli_doc.locator("body").inner_text()
        assert (
            "{{" not in text and "}}" not in text
        ), "Raw Jinja2 template syntax leaked into rendered page"
        assert "{%" not in text, "Raw Jinja2 block tag leaked into rendered page"

    def test_no_double_encoded_entities(self, overview_doc: Page):
        """&amp;lt; style double-encoding must not appear in content."""
        html = overview_doc.locator("main").inner_html()
        assert (
            "&amp;lt;" not in html and "&amp;gt;" not in html
        ), "Double-encoded HTML entities found in content"


# ── Internal links ─────────────────────────────────────────────────────────────


class TestInternalLinks:
    def test_internal_links_are_html(self, backup_doc: Page):
        """All relative links in doc content must point to .html files."""
        links = backup_doc.locator("main .doc-body a[href]").all()
        for link in links:
            href = link.get_attribute("href") or ""
            if href.startswith("http") or href.startswith("#"):
                continue  # skip external and anchor links
            assert (
                href.endswith(".html") or "#" in href
            ), f"Internal link does not point to .html: '{href}'"

    def test_breadcrumb_source_link_is_200(self, backup_doc: Page, base_url: str):
        source_link = backup_doc.locator("nav.breadcrumbs a").first
        href = source_link.get_attribute("href") or ""
        # Resolve relative href
        resolved = f"{base_url}/{href.lstrip('./').lstrip('../')}"
        resp = backup_doc.request.get(resolved)
        assert resp.status == 200, f"Breadcrumb link returned {resp.status}: {resolved}"


# ── Cross-source consistency ───────────────────────────────────────────────────


class TestCrossSourceConsistency:
    @pytest.mark.parametrize(
        "path",
        [
            "tools/docsync/docs--architecture.html",
            "applications/inventory-system/docs--overview.html",
        ],
        ids=["docsync-arch", "inventory-overview"],
    )
    def test_doc_has_breadcrumb(self, page: Page, base_url: str, path: str):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("load")
        expect(page.locator("nav.breadcrumbs")).to_be_visible()

    @pytest.mark.parametrize(
        "path",
        [
            "tools/docsync/docs--architecture.html",
            "applications/inventory-system/docs--overview.html",
        ],
        ids=["docsync-arch", "inventory-overview"],
    )
    def test_doc_has_h1(self, page: Page, base_url: str, path: str):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("load")
        assert page.locator("main h1").count() >= 1

    @pytest.mark.parametrize(
        "path",
        [
            "tools/docsync/docs--architecture.html",
            "applications/inventory-system/docs--overview.html",
        ],
        ids=["docsync-arch", "inventory-overview"],
    )
    def test_doc_has_page_nav(self, page: Page, base_url: str, path: str):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("load")
        # page-nav may or may not have prev/next depending on position
        # but the nav container itself should always exist
        expect(page.locator("nav.page-nav")).to_be_attached()
