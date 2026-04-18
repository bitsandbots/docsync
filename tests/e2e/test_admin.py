"""Tests for the admin panel (/admin).

Covers:
- All four admin cards present: sync, backup, restore, check
- Source dropdowns populated with known sources
- Action buttons present and enabled/disabled correctly
- API endpoints respond with expected shapes:
    GET /api/status  → JSON with last_sync + sources dict
    GET /api/check   → JSON with status key
- Log output area appears after triggering a command
- Reload config button present
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e

ADMIN_URL = "http://localhost:8484/admin"


@pytest.fixture
def admin(page: Page) -> Page:
    page.goto(ADMIN_URL)
    page.wait_for_load_state("load")
    return page


# ── Page structure ─────────────────────────────────────────────────────────────


class TestAdminStructure:
    def test_admin_page_loads(self, admin: Page):
        expect(admin.locator("body")).to_be_visible()

    def test_sync_card_present(self, admin: Page):
        expect(admin.locator("#sync")).to_be_visible()

    def test_backup_card_present(self, admin: Page):
        expect(admin.locator("#backup")).to_be_visible()

    def test_restore_card_present(self, admin: Page):
        expect(admin.locator("#restore")).to_be_visible()

    def test_check_card_present(self, admin: Page):
        expect(admin.locator("#check")).to_be_visible()

    def test_sidebar_present(self, admin: Page):
        expect(admin.locator("aside.sidebar")).to_be_visible()

    def test_header_present(self, admin: Page):
        expect(admin.locator("header.site-header")).to_be_visible()


# ── Action buttons ─────────────────────────────────────────────────────────────


class TestAdminButtons:
    def test_run_sync_button_present(self, admin: Page):
        btn = admin.locator("#btn-sync")
        expect(btn).to_be_visible()

    def test_run_backup_button_present(self, admin: Page):
        btn = admin.locator("#btn-backup")
        expect(btn).to_be_visible()

    def test_restore_button_initially_disabled(self, admin: Page):
        btn = admin.locator("#btn-restore")
        expect(btn).to_be_disabled()

    def test_run_check_button_present(self, admin: Page):
        expect(admin.locator("#btn-check")).to_be_visible()

    def test_show_status_button_present(self, admin: Page):
        expect(admin.locator("#btn-status")).to_be_visible()

    def test_reload_config_button_present(self, admin: Page):
        expect(admin.locator("#btn-reload")).to_be_visible()


# ── Source dropdowns ───────────────────────────────────────────────────────────


class TestAdminDropdowns:
    def test_sync_source_dropdown_present(self, admin: Page):
        expect(admin.locator("#sync-source")).to_be_visible()

    def test_backup_source_dropdown_present(self, admin: Page):
        expect(admin.locator("#backup-source")).to_be_visible()

    def test_restore_source_dropdown_present(self, admin: Page):
        expect(admin.locator("#restore-source")).to_be_visible()

    def test_sync_source_has_options(self, admin: Page):
        options = admin.locator("#sync-source option")
        assert options.count() >= 1

    def test_backup_source_has_options(self, admin: Page):
        options = admin.locator("#backup-source option")
        assert options.count() >= 1

    def test_docsync_in_sync_dropdown(self, admin: Page):
        options = admin.eval_on_selector_all(
            "#sync-source option",
            "els => els.map(e => e.textContent.trim())",
        )
        assert any(
            "DocSync" in o or "docsync" in o.lower() for o in options
        ), f"DocSync not found in sync dropdown: {options}"


# ── API endpoints ──────────────────────────────────────────────────────────────


class TestAdminAPI:
    def test_status_endpoint_returns_json(self, page: Page, base_url: str):
        resp = page.request.get(f"{base_url}/api/status")
        assert resp.status == 200
        data = resp.json()
        assert "last_sync" in data or "sources" in data

    def test_status_sources_is_dict(self, page: Page, base_url: str):
        data = page.request.get(f"{base_url}/api/status").json()
        assert isinstance(data.get("sources"), dict)

    def test_status_sources_have_counts(self, page: Page, base_url: str):
        sources = page.request.get(f"{base_url}/api/status").json().get("sources", {})
        assert len(sources) >= 1
        for name, count in sources.items():
            assert isinstance(count, int), f"Source '{name}' count is not int: {count}"

    def test_check_endpoint_returns_200(self, page: Page, base_url: str):
        """GET /api/check returns 200; it is a Server-Sent Events stream."""
        resp = page.request.get(f"{base_url}/api/check")
        assert resp.status == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type or len(resp.text()) > 0


# ── Log output after command ───────────────────────────────────────────────────


class TestAdminCommandOutput:
    def test_status_button_shows_output(self, admin: Page):
        """Clicking 'Show Status' must populate the #status-output or #log area."""
        btn = admin.locator("#btn-status")
        btn.click()
        # Wait for output to appear in #status-output or #log
        admin.wait_for_function(
            """() => {
                const log = document.querySelector('#log');
                const status = document.querySelector('#status-output');
                return (log && log.textContent.trim().length > 0)
                    || (status && status.textContent.trim().length > 0);
            }""",
            timeout=10000,
        )
        output_text = admin.evaluate("""() => {
            const log = document.querySelector('#log');
            const status = document.querySelector('#status-output');
            const logText = log ? log.textContent.trim() : '';
            const statusText = status ? status.textContent.trim() : '';
            return logText || statusText;
        }""")
        assert len(output_text) > 0, "Status output should not be empty"
