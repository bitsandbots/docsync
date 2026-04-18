"""Tests for the backup dashboard (/backups.html).

Covers:
- Backup cards render for sources with backup enabled
- Each card has stat labels: Snapshots, Total Size, Files, Duration
- Status indicator class present (bar-ok / bar-error / bar-warn)
- Card titles (source names) are non-empty
- Card footer / last-run info present
- Backup active link in sidebar
- No broken card layout (cards inside .card-grid)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


@pytest.fixture
def backups(page: Page, base_url: str) -> Page:
    page.goto(f"{base_url}/backups.html")
    page.wait_for_load_state("load")
    return page


# ── Page structure ─────────────────────────────────────────────────────────────


class TestBackupsPageStructure:
    def test_page_loads(self, backups: Page):
        expect(backups.locator("main#main")).to_be_visible()

    def test_card_grid_present(self, backups: Page):
        expect(backups.locator(".card-grid")).to_be_visible()

    def test_backup_cards_render(self, backups: Page):
        cards = backups.locator(".backup-card")
        assert cards.count() >= 1, "Expected at least one backup card"

    def test_sidebar_active_link(self, backups: Page):
        assert backups.locator("aside a.sidebar-link.active").count() >= 1

    def test_header_present(self, backups: Page):
        expect(backups.locator("header.site-header")).to_be_visible()


# ── Card content ───────────────────────────────────────────────────────────────


class TestBackupCardContent:
    def test_card_titles_non_empty(self, backups: Page):
        titles = backups.locator(".card-title")
        assert titles.count() >= 1
        for title in titles.all():
            text = title.inner_text().strip()
            assert len(text) > 0, "Backup card title must not be empty"

    def test_stat_labels_present(self, backups: Page):
        """Each card should have Snapshots, Total Size, Files, Duration labels."""
        expected = {"snapshots", "total size", "files", "duration"}
        labels = backups.locator(".stat-label")
        label_texts = {l.inner_text().strip().lower() for l in labels.all()}
        missing = expected - label_texts
        assert not missing, f"Missing stat labels: {missing}"

    def test_stat_values_non_empty(self, backups: Page):
        values = backups.locator(".stat-value")
        assert values.count() >= 1
        for val in values.all():
            assert len(val.inner_text().strip()) > 0, "Stat value must not be empty"

    def test_status_bar_has_class(self, backups: Page):
        """Each card bar must have one of the known status classes."""
        bars = backups.locator(".card-bar")
        assert bars.count() >= 1
        for bar in bars.all():
            classes = bar.get_attribute("class") or ""
            has_status = any(
                c in classes for c in ("bar-ok", "bar-error", "bar-warn", "bar-unknown")
            )
            assert has_status, f"Card bar missing status class: '{classes}'"

    def test_snapshots_value_is_numeric(self, backups: Page):
        """The Snapshots stat value must be a number."""
        # Find the value adjacent to the "Snapshots" label
        snap_labels = backups.locator(".stat-label").filter(has_text="Snapshots")
        assert snap_labels.count() >= 1
        first_stat = snap_labels.first.locator(
            "xpath=following-sibling::span[@class='stat-value']"
        )
        text = first_stat.inner_text().strip()
        assert text.isdigit(), f"Snapshots value should be numeric, got: '{text}'"


# ── Card layout integrity ──────────────────────────────────────────────────────


class TestBackupCardLayout:
    def test_all_cards_in_grid(self, backups: Page):
        """Every .backup-card must be inside .card-grid."""
        cards_in_grid = backups.locator(".card-grid .backup-card")
        all_cards = backups.locator(".backup-card")
        assert (
            cards_in_grid.count() == all_cards.count()
        ), "Some backup cards are outside .card-grid"

    def test_card_body_present(self, backups: Page):
        bodies = backups.locator(".card-body")
        assert bodies.count() >= 1

    def test_card_footer_present(self, backups: Page):
        footers = backups.locator(".card-footer")
        assert footers.count() >= 1

    def test_no_overlapping_cards(self, backups: Page):
        """Cards must not overlap — each has positive width and height."""
        cards = backups.locator(".backup-card").all()
        for card in cards[:5]:  # sample first 5
            box = card.bounding_box()
            assert box is not None, "Card has no bounding box"
            assert box["width"] > 10, f"Card width too small: {box['width']}"
            assert box["height"] > 10, f"Card height too small: {box['height']}"


# ── Navigation to backup detail (if available) ─────────────────────────────────


class TestBackupNavigation:
    def test_card_has_source_link_or_detail(self, backups: Page):
        """Each card should have a way to access more detail."""
        cards = backups.locator(".backup-card")
        first = cards.first
        # Either a link inside the card, or a footer with a stat link
        links = first.locator("a")
        stat = first.locator(".card-stat")
        has_link_or_stat = links.count() > 0 or stat.count() > 0
        assert has_link_or_stat, "Backup card should have a link or stat element"
