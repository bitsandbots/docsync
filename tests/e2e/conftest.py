"""Shared fixtures for Playwright end-to-end tests.

Run with:
    pytest tests/e2e/ -v --headed          # watch the browser
    pytest tests/e2e/ -v                   # headless (default)
    pytest tests/e2e/ -m e2e               # only e2e-marked tests
    pytest tests/e2e/ -k "nav"             # filter by name

Requires docsync-web running at base_url (default http://localhost:8484,
override with --base-url CLI flag or DOCSYNC_TEST_URL env var).

Uses system Chromium at /usr/bin/chromium — no `playwright install` needed.
"""

import os
import pytest
from playwright.sync_api import Page

# ── Browser configuration ──────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """Use system Chromium — no playwright install required."""
    return {
        "executable_path": os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium"),
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }


# ── Page fixtures — one per logical starting point ────────────────────────────


@pytest.fixture
def home(page: Page, base_url: str) -> Page:
    """Home page."""
    page.goto(base_url)
    page.wait_for_load_state("load")
    return page


@pytest.fixture
def inventory_index(page: Page, base_url: str) -> Page:
    """Inventory System source index — has all three nav tiers (README + Docs + Additional)."""
    page.goto(f"{base_url}/applications/inventory-system/index.html")
    page.wait_for_load_state("load")
    return page


@pytest.fixture
def docsync_index(page: Page, base_url: str) -> Page:
    """DocSync source index — Docs tier only, no root README."""
    page.goto(f"{base_url}/tools/docsync/index.html")
    page.wait_for_load_state("load")
    return page


@pytest.fixture
def arch_doc(page: Page, base_url: str) -> Page:
    """DocSync architecture doc — has prev/next nav and breadcrumbs."""
    page.goto(f"{base_url}/tools/docsync/docs--architecture.html")
    page.wait_for_load_state("load")
    return page


@pytest.fixture
def search_page(page: Page, base_url: str) -> Page:
    """Dedicated search page."""
    page.goto(f"{base_url}/search.html")
    page.wait_for_load_state("load")
    return page
