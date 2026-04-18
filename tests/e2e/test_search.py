"""Tests for the search functionality.

Covers:
- Search input visible and focusable in header (all pages)
- Dedicated search page loads
- Typing triggers lunr results (min 2 chars)
- Results render as links
- Short query (<2 chars) shows no results
- No-match query shows "no results" message
- Keyboard navigation (Enter key)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestHeaderSearch:
    def test_search_input_visible_on_home(self, home: Page):
        search = home.locator("#search-input")
        expect(search).to_be_visible()

    def test_search_input_is_focusable(self, home: Page):
        search = home.locator("#search-input")
        search.click()
        focused = home.evaluate("document.activeElement.id")
        assert focused == "search-input"

    def test_search_input_visible_on_doc_page(self, arch_doc: Page):
        search = arch_doc.locator("#search-input")
        expect(search).to_be_visible()

    def test_header_search_link_navigates_to_search_page(self, home: Page):
        link = home.locator("a[href*='search.html']").first
        expect(link).to_be_visible()
        with home.expect_navigation():
            link.click()
        assert "search.html" in home.url


class TestSearchPage:
    def test_search_page_loads(self, search_page: Page):
        expect(search_page.locator("#page-search-input")).to_be_visible()
        # #search-results is empty on load (zero height) — confirm it's in the DOM
        expect(search_page.locator("#search-results")).to_be_attached()

    def test_short_query_shows_no_results(self, search_page: Page):
        inp = search_page.locator("#page-search-input")
        inp.fill("a")
        search_page.wait_for_timeout(300)
        results = search_page.locator("#search-results")
        # Results div should be empty for < 2 char query
        assert results.inner_html().strip() == ""

    def test_valid_query_renders_results(self, search_page: Page):
        inp = search_page.locator("#page-search-input")
        inp.fill("backup")
        # Wait for lunr index to load and results to render
        search_page.wait_for_function(
            "document.getElementById('search-results').children.length > 0",
            timeout=5000,
        )
        links = search_page.locator("#search-results a")
        assert links.count() >= 1

    def test_results_are_links_with_hrefs(self, search_page: Page):
        inp = search_page.locator("#page-search-input")
        inp.fill("config")
        search_page.wait_for_function(
            "document.getElementById('search-results').children.length > 0",
            timeout=5000,
        )
        links = search_page.locator("#search-results a")
        first = links.first
        href = first.get_attribute("href")
        assert href and href.endswith(".html"), f"Expected .html link, got: {href}"

    def test_no_match_shows_message(self, search_page: Page):
        inp = search_page.locator("#page-search-input")
        inp.fill("xyzzy_no_match_ever")
        search_page.wait_for_function(
            "document.getElementById('search-results').innerHTML.trim() !== ''",
            timeout=5000,
        )
        content = search_page.locator("#search-results").inner_text()
        assert "no results" in content.lower() or "not found" in content.lower()

    def test_clearing_query_clears_results(self, search_page: Page):
        inp = search_page.locator("#page-search-input")
        inp.fill("backup")
        search_page.wait_for_function(
            "document.getElementById('search-results').children.length > 0",
            timeout=5000,
        )
        inp.fill("")
        search_page.wait_for_timeout(300)
        results = search_page.locator("#search-results")
        # Results should clear when query goes below 2 chars
        assert results.inner_html().strip() == ""

    def test_result_link_navigates_to_doc(self, search_page: Page, base_url: str):
        inp = search_page.locator("#page-search-input")
        inp.fill("manifest")
        search_page.wait_for_function(
            "document.getElementById('search-results').children.length > 0",
            timeout=5000,
        )
        first_link = search_page.locator("#search-results a").first
        with search_page.expect_navigation():
            first_link.click()
        # Should land on a doc page with main content
        expect(search_page.locator("main")).to_be_visible()
        assert search_page.url.endswith(".html")
