"""Responsive layout tests across viewport breakpoints.

Breakpoints from style.css:
  >1024px  — desktop: sidebar visible, toggle hidden
   900px   — sidebar narrows
   700px   — sidebar hidden, toggle shown, overlay nav
   480px   — mobile: smaller padding, stacked layout

Covers:
- Sidebar visibility at each breakpoint
- Toggle button visibility/hiddenness
- Main content remains accessible at all sizes
- Sidebar opens/closes via toggle at mobile widths
- Search input accessible at mobile widths
- Footer visible at all widths
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

DESKTOP = {"width": 1440, "height": 900}
LAPTOP = {"width": 1024, "height": 768}
TABLET = {"width": 900, "height": 1024}
MOBILE_LG = {"width": 700, "height": 900}
MOBILE_SM = {"width": 375, "height": 812}


def goto_home(page: Page, base_url: str, viewport: dict) -> None:
    page.set_viewport_size(viewport)
    page.goto(base_url)
    page.wait_for_load_state("load")


# ── Desktop ────────────────────────────────────────────────────────────────────


class TestDesktop:
    def test_sidebar_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, DESKTOP)
        expect(page.locator("aside.sidebar")).to_be_visible()

    def test_toggle_hidden(self, page: Page, base_url: str):
        goto_home(page, base_url, DESKTOP)
        toggle = page.locator("#sidebar-toggle")
        # display:none at desktop — Playwright considers it hidden
        assert not toggle.is_visible()

    def test_main_content_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, DESKTOP)
        expect(page.locator("main#main")).to_be_visible()

    def test_header_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, DESKTOP)
        expect(page.locator("header.site-header")).to_be_visible()

    def test_search_input_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, DESKTOP)
        expect(page.locator("#search-input")).to_be_visible()


# ── Laptop / narrow desktop ────────────────────────────────────────────────────


class TestLaptop:
    def test_sidebar_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, LAPTOP)
        expect(page.locator("aside.sidebar")).to_be_visible()

    def test_main_content_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, LAPTOP)
        expect(page.locator("main#main")).to_be_visible()

    def test_footer_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, LAPTOP)
        expect(page.locator("footer.site-footer")).to_be_visible()


# ── Tablet ─────────────────────────────────────────────────────────────────────


class TestTablet:
    def test_main_content_accessible(self, page: Page, base_url: str):
        goto_home(page, base_url, TABLET)
        expect(page.locator("main#main")).to_be_visible()

    def test_header_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, TABLET)
        expect(page.locator("header.site-header")).to_be_visible()

    def test_search_input_present(self, page: Page, base_url: str):
        goto_home(page, base_url, TABLET)
        expect(page.locator("#search-input")).to_be_attached()


# ── Mobile large (≤700px — sidebar collapses) ─────────────────────────────────


class TestMobileLarge:
    def test_toggle_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_LG)
        expect(page.locator("#sidebar-toggle")).to_be_visible()

    def test_main_content_accessible(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_LG)
        expect(page.locator("main#main")).to_be_visible()

    def test_sidebar_toggle_opens_sidebar(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_LG)
        toggle = page.locator("#sidebar-toggle")
        expect(toggle).to_be_visible()
        toggle.click()
        page.wait_for_timeout(300)
        # Sidebar or overlay should now be active
        sidebar = page.locator("aside.sidebar")
        overlay = page.locator("#sidebar-overlay")
        sidebar_open = sidebar.is_visible() or page.evaluate(
            "document.body.classList.contains('sidebar-open')"
        )
        overlay_active = page.evaluate(
            "document.getElementById('sidebar-overlay')?.classList.contains('active') "
            "|| false"
        )
        assert sidebar_open or overlay_active, "Sidebar should open after toggle click"

    def test_toggle_closes_sidebar(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_LG)
        toggle = page.locator("#sidebar-toggle")
        toggle.click()
        page.wait_for_timeout(200)
        toggle.click()
        page.wait_for_timeout(200)
        # After two clicks, sidebar should be closed again
        overlay_active = page.evaluate(
            "document.getElementById('sidebar-overlay')?.classList.contains('active') "
            "|| false"
        )
        assert not overlay_active, "Sidebar should close after second toggle click"

    def test_no_horizontal_overflow(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_LG)
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        client_width = page.evaluate("document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2, (
            f"Horizontal overflow at {MOBILE_LG['width']}px: "
            f"scrollWidth={scroll_width} > clientWidth={client_width}"
        )


# ── Mobile small (375px) ───────────────────────────────────────────────────────


class TestMobileSmall:
    def test_toggle_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_SM)
        expect(page.locator("#sidebar-toggle")).to_be_visible()

    def test_main_content_accessible(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_SM)
        expect(page.locator("main#main")).to_be_visible()

    def test_header_visible(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_SM)
        expect(page.locator("header.site-header")).to_be_visible()

    def test_doc_page_readable_at_mobile(self, page: Page, base_url: str):
        """Doc page content must be accessible at 375px."""
        page.set_viewport_size(MOBILE_SM)
        page.goto(f"{base_url}/tools/docsync/docs--architecture.html")
        page.wait_for_load_state("load")
        expect(page.locator("main#main")).to_be_visible()
        h1 = page.locator("main h1").first
        expect(h1).to_be_visible()

    def test_no_horizontal_overflow(self, page: Page, base_url: str):
        goto_home(page, base_url, MOBILE_SM)
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        client_width = page.evaluate("document.documentElement.clientWidth")
        assert scroll_width <= client_width + 2, (
            f"Horizontal overflow at {MOBILE_SM['width']}px: "
            f"scrollWidth={scroll_width} > clientWidth={client_width}"
        )


# ── Cross-viewport consistency ─────────────────────────────────────────────────


class TestCrossViewport:
    @pytest.mark.parametrize(
        "viewport",
        [DESKTOP, LAPTOP, TABLET, MOBILE_LG, MOBILE_SM],
        ids=["desktop", "laptop", "tablet", "mobile-lg", "mobile-sm"],
    )
    def test_site_title_always_visible(self, page: Page, base_url: str, viewport):
        goto_home(page, base_url, viewport)
        logo = page.locator("header .site-logo, header .brand-name").first
        expect(logo).to_be_visible()

    @pytest.mark.parametrize(
        "viewport",
        [DESKTOP, LAPTOP, MOBILE_SM],
        ids=["desktop", "laptop", "mobile-sm"],
    )
    def test_search_input_attached_at_all_sizes(
        self, page: Page, base_url: str, viewport
    ):
        goto_home(page, base_url, viewport)
        expect(page.locator("#search-input")).to_be_attached()
