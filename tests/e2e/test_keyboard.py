"""Keyboard navigation tests.

Covers:
- Skip link is first focusable element and jumps to #main
- Tab reaches search input in header
- Tab reaches theme toggle
- Details/summary collapsibles toggle with Enter and Space
- Sidebar source links are reachable via Tab
- Active element tracking (no focus lost)
- Escape key behaviour in search
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

DOCS_LABEL = re.compile(r"^Docs$", re.IGNORECASE)


class TestSkipLink:
    def test_skip_link_is_first_focusable(self, home: Page):
        """Tab from body lands on the skip link before anything else."""
        home.keyboard.press("Tab")
        focused_id = home.evaluate("document.activeElement.className")
        assert "skip-link" in focused_id

    def test_skip_link_activates_on_enter(self, home: Page):
        """Enter on the skip link moves focus to #main."""
        home.keyboard.press("Tab")  # focus skip link
        home.keyboard.press("Enter")
        focused = home.evaluate("document.activeElement.id")
        # main should receive focus or be the scrollTarget
        assert focused == "main" or home.evaluate(
            "document.activeElement.closest('#main') !== null"
        )

    def test_skip_link_href_is_main(self, home: Page):
        skip = home.locator("a.skip-link")
        assert skip.get_attribute("href") == "#main"


class TestTabOrder:
    def test_tab_reaches_search_input(self, home: Page):
        """Tabbing from the start of the page should eventually focus #search-input."""
        for _ in range(20):
            home.keyboard.press("Tab")
            focused = home.evaluate("document.activeElement.id")
            if focused == "search-input":
                return
        pytest.fail("#search-input never received focus after 20 Tab presses")

    def test_tab_reaches_theme_toggle(self, home: Page):
        for _ in range(20):
            home.keyboard.press("Tab")
            focused = home.evaluate("document.activeElement.id")
            if focused == "theme-toggle":
                return
        pytest.fail("#theme-toggle never received focus after 20 Tab presses")

    def test_no_focus_trapped_in_header(self, home: Page):
        """Tabbing past the header should reach sidebar or main content."""
        seen = set()
        for _ in range(30):
            home.keyboard.press("Tab")
            focused = home.evaluate("document.activeElement.id || ''")
            seen.add(focused)
        # Focus should have moved beyond header elements
        assert len(seen) > 3, "Focus appears trapped — only visited: " + str(seen)


class TestCollapsibleKeyboard:
    def test_enter_opens_docs_section(self, docsync_index: Page):
        """Enter on the 'Docs' summary must open the details."""
        summary = docsync_index.locator(
            ".sidebar-additional summary.sidebar-additional-label"
        ).filter(has_text=DOCS_LABEL)
        details = docsync_index.locator("details.sidebar-additional").filter(
            has=docsync_index.locator("summary").filter(has_text=DOCS_LABEL)
        )
        summary.focus()
        initial = details.evaluate("el => el.open")
        docsync_index.keyboard.press("Enter")
        after = details.evaluate("el => el.open")
        assert after != initial, "Enter should toggle the details element"

    def test_space_toggles_docs_section(self, docsync_index: Page):
        """Space on the 'Docs' summary must toggle the details."""
        summary = docsync_index.locator(
            ".sidebar-additional summary.sidebar-additional-label"
        ).filter(has_text=DOCS_LABEL)
        details = docsync_index.locator("details.sidebar-additional").filter(
            has=docsync_index.locator("summary").filter(has_text=DOCS_LABEL)
        )
        summary.focus()
        initial = details.evaluate("el => el.open")
        docsync_index.keyboard.press("Space")
        after = details.evaluate("el => el.open")
        assert after != initial, "Space should toggle the details element"

    def test_focused_summary_has_visible_outline(self, docsync_index: Page):
        """Focused summary must have a visible outline (not outline:none)."""
        summary = docsync_index.locator(
            ".sidebar-additional summary.sidebar-additional-label"
        ).filter(has_text=DOCS_LABEL)
        summary.focus()
        outline = docsync_index.evaluate("""() => {
                const el = document.activeElement;
                const style = window.getComputedStyle(el);
                return style.outlineStyle + '|' + style.outlineWidth;
            }""")
        # outline:none with no box-shadow = invisible focus — should not happen
        style, width = outline.split("|")
        assert not (style == "none" and width == "0px"), (
            f"Summary has no visible focus outline: outline-style={style}, "
            f"outline-width={width}"
        )


class TestSearchKeyboard:
    def test_typing_in_search_shows_results(self, search_page: Page):
        """Typing into #page-search-input without clicking must work."""
        inp = search_page.locator("#page-search-input")
        inp.focus()
        search_page.keyboard.type("backup")
        search_page.wait_for_function(
            "document.getElementById('search-results').children.length > 0",
            timeout=5000,
        )
        assert search_page.locator("#search-results a").count() >= 1

    def test_escape_clears_header_search(self, home: Page):
        """Escape after typing in header search clears or blurs it."""
        inp = home.locator("#search-input")
        inp.focus()
        home.keyboard.type("backup")
        home.keyboard.press("Escape")
        home.wait_for_timeout(200)
        # Either value is cleared or focus has moved away
        value = inp.input_value()
        focused = home.evaluate("document.activeElement.id")
        assert value == "" or focused != "search-input"


class TestSidebarKeyboardNav:
    def test_sidebar_links_are_keyboard_focusable(self, home: Page):
        """All sidebar source links must be reachable via Tab (have tabindex ≥ 0)."""
        links = home.locator("aside a.sidebar-link").all()
        for link in links[:5]:  # sample first 5
            tab_index = link.evaluate("el => el.tabIndex")  # -1 = not reachable
            assert (
                tab_index >= 0
            ), f"Link '{link.inner_text().strip()}' has tabIndex={tab_index}"

    def test_enter_on_source_link_navigates(self, home: Page):
        """Enter on a source link (focused via Tab) navigates to that source."""
        # Tab to first source link with an icon
        source_link = (
            home.locator("aside a.sidebar-link")
            .filter(has=home.locator("svg.icon"))
            .first
        )
        source_link.focus()
        href = source_link.get_attribute("href")
        with home.expect_navigation():
            home.keyboard.press("Enter")
        expect(home.locator("main")).to_be_visible()
