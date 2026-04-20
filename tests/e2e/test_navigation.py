"""Tests for the three-tier sidebar navigation structure.

Covers:
- README pinned at top (always visible)
- Docs collapsible section (docs/ folder content)
- Additional Docs collapsible section (other root-level files)
- Active state highlighting on current page
- Auto-expand of the correct section when navigating to a doc
- Category labels
- Source count badges
- Sidebar collapse/expand (mobile toggle)
"""

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

# Exact-match selectors for the two collapsible labels.
# Case-insensitive because CSS text-transform:uppercase affects inner_text().
# "Docs" must not match "Additional Docs".
DOCS_LABEL = re.compile(r"^Docs$", re.IGNORECASE)
ADDITIONAL_LABEL = re.compile(r"^Additional Docs$", re.IGNORECASE)


# ── Home page structure ────────────────────────────────────────────────────────


class TestHomeNavStructure:
    def test_sidebar_is_visible(self, home: Page):
        expect(home.locator("aside.sidebar")).to_be_visible()

    def test_category_labels_render(self, home: Page):
        # At minimum "Navigation" + at least one project category
        assert home.locator(".sidebar-label").count() >= 2

    def test_source_links_render(self, home: Page):
        sources = home.locator("aside .sidebar-link").filter(
            has=home.locator("svg.icon")
        )
        assert sources.count() >= 1

    def test_source_count_badges_render(self, home: Page):
        badges = home.locator("aside .sidebar-link span[style*='font-size']")
        assert badges.count() >= 1

    def test_home_link_is_active(self, home: Page):
        expect(home.locator("aside .sidebar-link.active").first).to_be_visible()


# ── Three-tier sidebar on a source with all tiers ─────────────────────────────


class TestThreeTierNavInventory:
    """Inventory System has: README + docs/ + additional docs."""

    def test_readme_link_visible_at_top(self, inventory_index: Page):
        readme = inventory_index.locator(".sidebar-project a.sidebar-link").first
        expect(readme).to_be_visible()
        expect(readme).to_contain_text("Readme")

    def test_docs_section_present(self, inventory_index: Page):
        summary = inventory_index.locator(
            ".sidebar-additional summary.sidebar-additional-label"
        ).filter(has_text=DOCS_LABEL)
        expect(summary).to_have_count(1)

    def test_additional_docs_section_present(self, inventory_index: Page):
        summary = inventory_index.locator(
            ".sidebar-additional summary.sidebar-additional-label"
        ).filter(has_text=ADDITIONAL_LABEL)
        expect(summary).to_have_count(1)

    def test_docs_section_contains_links(self, inventory_index: Page):
        docs_details = inventory_index.locator("details.sidebar-additional").filter(
            has=inventory_index.locator("summary.sidebar-additional-label").filter(
                has_text=DOCS_LABEL
            )
        )
        assert docs_details.locator("a.sidebar-link").count() >= 1

    def test_readme_appears_before_docs_section(self, inventory_index: Page):
        """README link must come before the first <details> in the sidebar."""
        elements = inventory_index.locator(
            ".sidebar-project > a.sidebar-link, .sidebar-project > details"
        ).all()
        assert len(elements) >= 2, "Expected README link + at least one details section"
        first_tag = elements[0].evaluate("el => el.tagName.toLowerCase()")
        assert first_tag == "a", f"Expected <a> (README) first, got <{first_tag}>"

    def test_docs_section_before_additional(self, inventory_index: Page):
        """'Docs' details must appear before 'Additional Docs' details."""
        details = inventory_index.locator("details.sidebar-additional").all()
        # inner_text() reflects CSS text-transform:uppercase — normalise to lowercase
        labels = [d.locator("summary").inner_text().strip().lower() for d in details]
        assert "docs" in labels and "additional docs" in labels
        assert labels.index("docs") < labels.index("additional docs")


# ── Source with README + Docs ──────────────────────────────────────────────────


class TestDocSyncNavStructure:
    """DocSync source has README + docs/ content — tests README-first ordering.

    Note: The 'no README' case (primary_docs only, readme_doc=None) is covered by
    unit tests in tests/test_generator.py::TestNavTreeBuilder::test_docs_folder_goes_to_primary.
    """

    def test_readme_link_at_top(self, docsync_index: Page):
        """README link must appear first, before any <details> sections."""
        first = docsync_index.locator(".sidebar-project > *").first
        tag = first.evaluate("el => el.tagName.toLowerCase()")
        assert tag == "a", f"Expected <a> first (README link), got <{tag}>"
        # Verify it's actually the README link
        href = first.evaluate("el => el.getAttribute('href')")
        assert "readme" in href.lower(), f"Expected README href, got {href}"

    def test_docs_section_present(self, docsync_index: Page):
        summary = docsync_index.locator(
            ".sidebar-additional summary.sidebar-additional-label"
        ).filter(has_text=DOCS_LABEL)
        expect(summary).to_have_count(1)

    def test_docs_section_has_links(self, docsync_index: Page):
        details = docsync_index.locator("details.sidebar-additional").filter(
            has=docsync_index.locator("summary").filter(has_text=DOCS_LABEL)
        )
        assert details.locator("a.sidebar-link").count() >= 5


# ── Auto-expand behavior ────────────────────────────────────────────────────────


class TestAutoExpand:
    def test_docs_section_open_when_viewing_docs_page(self, arch_doc: Page):
        """'Docs' <details> must be open when a doc from docs/ is active."""
        docs_details = arch_doc.locator("details.sidebar-additional").filter(
            has=arch_doc.locator("summary").filter(has_text=DOCS_LABEL)
        )
        is_open = docs_details.evaluate("el => el.open")
        assert is_open, "'Docs' details should be auto-expanded on a docs/ page"

    def test_active_link_highlighted_in_docs_section(self, arch_doc: Page):
        active_link = arch_doc.locator(
            "details.sidebar-additional a.sidebar-link.active"
        )
        expect(active_link).to_have_count(1)
        expect(active_link).to_contain_text("Architecture")


# ── Collapsible toggle ─────────────────────────────────────────────────────────


class TestCollapsibleSections:
    def test_docs_section_toggles_open_on_click(self, docsync_index: Page):
        details = docsync_index.locator("details.sidebar-additional").filter(
            has=docsync_index.locator("summary").filter(has_text=DOCS_LABEL)
        )
        summary = details.locator("summary")
        initial = details.evaluate("el => el.open")
        summary.click()
        after_click = details.evaluate("el => el.open")
        assert after_click != initial, "Click should toggle the details open state"

    def test_sidebar_toggle_visible_on_mobile(self, page: Page, base_url: str):
        """Toggle button is only shown at ≤700px — use mobile viewport."""
        page.set_viewport_size({"width": 480, "height": 800})
        page.goto(base_url)
        page.wait_for_load_state("load")
        toggle = page.locator("#sidebar-toggle")
        expect(toggle).to_be_visible()

    def test_sidebar_toggle_click_on_mobile(self, page: Page, base_url: str):
        """Clicking the toggle at mobile viewport does not raise an error."""
        page.set_viewport_size({"width": 480, "height": 800})
        page.goto(base_url)
        page.wait_for_load_state("load")
        toggle = page.locator("#sidebar-toggle")
        expect(toggle).to_be_visible()
        toggle.click()
        page.wait_for_timeout(200)
        # Sidebar or overlay state changed — no JS error is sufficient
        expect(page.locator("body")).to_be_visible()


# ── Navigation link integrity ──────────────────────────────────────────────────


class TestNavLinkIntegrity:
    def test_sidebar_links_have_valid_hrefs(self, home: Page):
        links = home.locator("aside a.sidebar-link").all()
        assert len(links) > 0
        for link in links:
            href = link.get_attribute("href")
            assert href and href.strip(), f"Empty href on link: {link.inner_text()}"

    def test_readme_link_navigates_successfully(self, inventory_index: Page):
        readme_link = inventory_index.locator(".sidebar-project > a.sidebar-link").first
        with inventory_index.expect_navigation():
            readme_link.click()
        assert inventory_index.url.endswith("readme.html")
        expect(inventory_index.locator("main")).to_be_visible()

    def test_doc_link_in_docs_section_navigates(self, docsync_index: Page):
        docs_details = docsync_index.locator("details.sidebar-additional").filter(
            has=docsync_index.locator("summary").filter(has_text=DOCS_LABEL)
        )
        docs_details.locator("summary").click()
        first_link = docs_details.locator("a.sidebar-link").first
        with docsync_index.expect_navigation():
            first_link.click()
        expect(docsync_index.locator("main")).to_be_visible()
        assert docsync_index.url.endswith(".html")
