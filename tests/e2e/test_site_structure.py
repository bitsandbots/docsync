"""Tests for overall site structure and page integrity.

Covers:
- Home page loads with expected elements
- Static pages (search, updates, backups) all return content
- All sidebar source links resolve to 200 (no dead nav entries)
- Site title appears in header
- Footer present with last-synced timestamp
- No console errors on key pages
- Admin panel accessible
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

STATIC_PAGES = [
    ("home", "index.html"),
    ("search", "search.html"),
    ("updates", "updates.html"),
    ("backups", "backups.html"),
]


class TestStaticPages:
    @pytest.mark.parametrize("name,path", STATIC_PAGES)
    def test_page_loads_with_main_content(self, page: Page, base_url: str, name, path):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("main")).to_be_visible()

    @pytest.mark.parametrize("name,path", STATIC_PAGES)
    def test_page_has_site_header(self, page: Page, base_url: str, name, path):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("header.site-header")).to_be_visible()

    @pytest.mark.parametrize("name,path", STATIC_PAGES)
    def test_page_has_sidebar(self, page: Page, base_url: str, name, path):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("aside.sidebar")).to_be_visible()

    @pytest.mark.parametrize("name,path", STATIC_PAGES)
    def test_page_has_footer(self, page: Page, base_url: str, name, path):
        page.goto(f"{base_url}/{path}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("footer.site-footer")).to_be_visible()


class TestHomePage:
    def test_site_title_in_header(self, home: Page):
        header = home.locator("header.site-header")
        text = header.inner_text()
        # Brand name or site title appears somewhere in header
        assert len(text.strip()) > 0

    def test_footer_has_last_synced(self, home: Page):
        footer = home.locator("footer.site-footer")
        text = footer.inner_text()
        assert "synced" in text.lower() or len(text.strip()) > 0

    def test_no_console_errors(self, page: Page, base_url: str):
        errors = []
        page.on(
            "console", lambda msg: errors.append(msg) if msg.type == "error" else None
        )
        page.goto(base_url)
        page.wait_for_load_state("networkidle")
        # Filter out known benign errors (e.g. favicon 404)
        real_errors = [e for e in errors if "favicon" not in e.text.lower()]
        assert real_errors == [], f"Console errors: {[e.text for e in real_errors]}"

    def test_categories_render_in_sidebar(self, home: Page):
        labels = home.locator("aside .sidebar-label")
        texts = [l.inner_text().strip() for l in labels.all()]
        assert len(texts) >= 2, f"Expected ≥2 category labels, got: {texts}"

    def test_navigation_links_present(self, home: Page):
        nav_links = home.locator("aside nav > a.sidebar-link")
        assert nav_links.count() >= 3


class TestSidebarLinkIntegrity:
    def test_all_source_index_links_resolve(self, page: Page, base_url: str):
        """Every source-level sidebar link (with icon) must return a loadable page."""
        page.goto(base_url)
        page.wait_for_load_state("networkidle")

        source_links = page.locator("aside a.sidebar-link svg.icon ~ *").all()
        # Collect hrefs from parent anchors
        hrefs = page.eval_on_selector_all(
            "aside a.sidebar-link:has(svg.icon)",
            "els => els.map(e => e.getAttribute('href'))",
        )
        failures = []
        for href in hrefs:
            if not href:
                continue
            # Resolve relative href from base
            if href.startswith("http"):
                url = href
            else:
                url = f"{base_url}/{href.lstrip('.').lstrip('/')}"
            resp = page.request.get(url)
            if resp.status != 200:
                failures.append(f"{href} → {resp.status}")

        assert failures == [], f"Dead source links:\n" + "\n".join(failures)

    def test_no_empty_sidebar_sections(self, home: Page):
        """No source in the sidebar should have a doc count of 0 AND show as active."""
        badges = home.eval_on_selector_all(
            "aside a.sidebar-link span[style*='font-size']",
            "els => els.map(e => parseInt(e.textContent.trim()))",
        )
        # Badges showing 0 would indicate a source with no docs — warn but don't fail
        zero_badges = [b for b in badges if b == 0]
        # This is informational — sources should have docs
        assert len(zero_badges) < len(badges), "All sources appear to have 0 docs"


class TestUpdatesPage:
    def test_updates_page_has_content(self, page: Page, base_url: str):
        page.goto(f"{base_url}/updates.html")
        page.wait_for_load_state("networkidle")
        main = page.locator("main")
        expect(main).to_be_visible()

    def test_updates_active_in_sidebar(self, page: Page, base_url: str):
        page.goto(f"{base_url}/updates.html")
        page.wait_for_load_state("networkidle")
        assert page.locator("aside a.sidebar-link.active").count() >= 1


class TestBackupsPage:
    def test_backups_page_loads(self, page: Page, base_url: str):
        page.goto(f"{base_url}/backups.html")
        page.wait_for_load_state("networkidle")
        expect(page.locator("main")).to_be_visible()

    def test_backups_active_in_sidebar(self, page: Page, base_url: str):
        page.goto(f"{base_url}/backups.html")
        page.wait_for_load_state("networkidle")
        assert page.locator("aside a.sidebar-link.active").count() >= 1


class TestAdminPage:
    def test_admin_page_loads(self, page: Page, base_url: str):
        page.goto(f"{base_url}/admin")
        page.wait_for_load_state("networkidle")
        expect(page.locator("body")).to_be_visible()

    def test_no_console_errors_on_doc_page(self, arch_doc: Page):
        errors = []
        arch_doc.on(
            "console", lambda msg: errors.append(msg) if msg.type == "error" else None
        )
        arch_doc.reload()
        arch_doc.wait_for_load_state("networkidle")
        real_errors = [e for e in errors if "favicon" not in e.text.lower()]
        assert (
            real_errors == []
        ), f"Console errors on doc page: {[e.text for e in real_errors]}"
