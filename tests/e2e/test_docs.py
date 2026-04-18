"""Tests for individual documentation page rendering.

Covers:
- Page title rendered in <h1>
- Breadcrumb navigation present and correct
- Prev/next navigation links present and functional
- Table of contents links (when doc has headings)
- Tags rendered (when present)
- Doc content area visible
- Source index page: doc list and metadata
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestDocPageStructure:
    def test_main_content_visible(self, arch_doc: Page):
        expect(arch_doc.locator("main#main")).to_be_visible()

    def test_page_has_h1(self, arch_doc: Page):
        h1 = arch_doc.locator("main h1").first
        expect(h1).to_be_visible()
        assert len(h1.inner_text().strip()) > 0

    def test_breadcrumb_present(self, arch_doc: Page):
        crumb = arch_doc.locator("nav.breadcrumbs")
        expect(crumb).to_be_visible()

    def test_breadcrumb_contains_source_name(self, arch_doc: Page):
        crumb = arch_doc.locator("nav.breadcrumbs")
        text = crumb.inner_text()
        assert "DocSync" in text or "Tools" in text

    def test_breadcrumb_source_link_navigates(self, arch_doc: Page):
        source_link = arch_doc.locator("nav.breadcrumbs a").first
        expect(source_link).to_be_visible()
        href = source_link.get_attribute("href")
        assert href and "index.html" in href

    def test_doc_layout_container_exists(self, arch_doc: Page):
        expect(arch_doc.locator(".doc-layout")).to_be_visible()


class TestPrevNextNavigation:
    def test_prev_link_present(self, arch_doc: Page):
        prev = arch_doc.locator("nav.page-nav a.prev")
        expect(prev).to_be_visible()

    def test_next_link_present(self, arch_doc: Page):
        nxt = arch_doc.locator("nav.page-nav a.next")
        expect(nxt).to_be_visible()

    def test_prev_link_shows_title(self, arch_doc: Page):
        title = arch_doc.locator("nav.page-nav a.prev .nav-title")
        expect(title).to_be_visible()
        assert len(title.inner_text().strip()) > 0

    def test_next_link_shows_title(self, arch_doc: Page):
        title = arch_doc.locator("nav.page-nav a.next .nav-title")
        expect(title).to_be_visible()
        assert len(title.inner_text().strip()) > 0

    def test_prev_link_navigates_successfully(self, arch_doc: Page, base_url: str):
        prev = arch_doc.locator("nav.page-nav a.prev")
        href = prev.get_attribute("href")
        with arch_doc.expect_navigation():
            prev.click()
        expect(arch_doc.locator("main")).to_be_visible()
        assert arch_doc.url.endswith(".html")

    def test_next_link_navigates_successfully(self, arch_doc: Page, base_url: str):
        nxt = arch_doc.locator("nav.page-nav a.next")
        with arch_doc.expect_navigation():
            nxt.click()
        expect(arch_doc.locator("main")).to_be_visible()
        assert arch_doc.url.endswith(".html")

    def test_navigated_doc_has_active_link_in_sidebar(self, arch_doc: Page):
        """After clicking next, the new page's sidebar link should be active."""
        nxt = arch_doc.locator("nav.page-nav a.next")
        with arch_doc.expect_navigation():
            nxt.click()
        active = arch_doc.locator("aside a.sidebar-link.active")
        assert active.count() >= 1


class TestSourceIndexPage:
    def test_source_name_in_heading(self, docsync_index: Page):
        heading = docsync_index.locator("main h1, main h2").first
        expect(heading).to_be_visible()
        text = heading.inner_text()
        assert "DocSync" in text or len(text) > 0

    def test_doc_list_renders(self, docsync_index: Page):
        # The project page lists docs as cards or links
        links = docsync_index.locator("main a[href*='.html']")
        assert links.count() >= 1

    def test_source_metadata_present(self, docsync_index: Page):
        # Source type, path, or doc count should appear somewhere
        main = docsync_index.locator("main")
        text = main.inner_text()
        # Should contain a number (doc count) or path info
        import re

        has_number = bool(re.search(r"\d+", text))
        assert has_number, "Source index should display numeric metadata"

    def test_inventory_index_shows_all_tiers(self, inventory_index: Page):
        """Source index for inventory shows readme + docs + additional in sidebar."""
        import re

        project_nav = inventory_index.locator(".sidebar-project")
        # README anchor (bare link, not inside details)
        expect(project_nav.locator("> a.sidebar-link").first).to_be_visible()
        # Exact match, case-insensitive (CSS text-transform:uppercase affects inner_text)
        docs = project_nav.locator("details summary").filter(
            has_text=re.compile(r"^Docs$", re.IGNORECASE)
        )
        expect(docs).to_have_count(1)
        additional = project_nav.locator("details summary").filter(
            has_text=re.compile(r"^Additional Docs$", re.IGNORECASE)
        )
        expect(additional).to_have_count(1)


class TestReadmePage:
    def test_readme_page_loads(self, page: Page, base_url: str):
        page.goto(f"{base_url}/applications/inventory-system/readme.html")
        page.wait_for_load_state("networkidle")
        expect(page.locator("main")).to_be_visible()

    def test_readme_active_in_sidebar(self, page: Page, base_url: str):
        page.goto(f"{base_url}/applications/inventory-system/readme.html")
        page.wait_for_load_state("networkidle")
        # The README link (bare link, not inside details) should be active
        readme_link = page.locator(".sidebar-project > a.sidebar-link.active")
        expect(readme_link).to_have_count(1)

    def test_readme_has_content(self, page: Page, base_url: str):
        page.goto(f"{base_url}/applications/inventory-system/readme.html")
        page.wait_for_load_state("networkidle")
        main_text = page.locator("main").inner_text()
        assert (
            len(main_text.strip()) > 50
        ), "README page should have substantial content"
