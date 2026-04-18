"""Tests for theme toggle and accessibility controls.

Covers:
- Theme toggle button present and labelled
- Clicking cycles dark/light (data-theme or body class)
- Preference written to localStorage
- Fresh page load respects saved preference
- High contrast toggle
- Dyslexia-friendly font toggle
- Skip link present (a11y)
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestThemeToggle:
    def test_toggle_button_is_visible(self, home: Page):
        btn = home.locator("#theme-toggle")
        expect(btn).to_be_visible()

    def test_toggle_has_accessible_label(self, home: Page):
        btn = home.locator("#theme-toggle")
        label = btn.get_attribute("aria-label")
        assert label and ("dark" in label.lower() or "theme" in label.lower())

    def test_clicking_toggle_changes_theme(self, home: Page):
        btn = home.locator("#theme-toggle")
        initial = home.evaluate(
            "document.documentElement.getAttribute('data-theme') "
            "|| document.body.className"
        )
        btn.click()
        home.wait_for_timeout(100)
        after = home.evaluate(
            "document.documentElement.getAttribute('data-theme') "
            "|| document.body.className"
        )
        assert initial != after, "Theme should change after toggle click"

    def test_theme_written_to_localstorage(self, page: Page, base_url: str):
        page.goto(base_url)
        page.wait_for_load_state("load")
        page.evaluate("localStorage.clear()")  # start clean
        page.locator("#theme-toggle").click()
        page.wait_for_timeout(100)
        stored = page.evaluate("localStorage.getItem('docsync-theme')")
        assert stored in ("dark", "light"), f"Expected dark or light, got: {stored!r}"

    def test_saved_dark_theme_applied_on_load(self, page: Page, base_url: str):
        """Page loaded with dark saved in localStorage should start dark."""
        page.goto(base_url)
        page.evaluate("localStorage.setItem('docsync-theme', 'dark')")
        page.reload()
        page.wait_for_load_state("load")
        theme = page.evaluate(
            "document.documentElement.getAttribute('data-theme') "
            "|| document.body.className"
        )
        assert "dark" in str(theme)
        page.evaluate("localStorage.clear()")  # clean up so other tests start fresh

    def test_saved_light_theme_applied_on_load(self, page: Page, base_url: str):
        page.goto(base_url)
        page.evaluate("localStorage.setItem('docsync-theme', 'light')")
        page.reload()
        page.wait_for_load_state("load")
        theme = page.evaluate(
            "document.documentElement.getAttribute('data-theme') "
            "|| document.body.className"
        )
        assert "dark" not in str(theme)
        page.evaluate("localStorage.clear()")

    def test_sun_moon_icons_swap(self, home: Page):
        moon = home.locator("#theme-icon-moon")
        sun = home.locator("#theme-icon-sun")
        # Initially moon visible, sun hidden
        moon_vis = moon.is_visible()
        sun_vis = sun.is_visible()
        assert moon_vis != sun_vis, "Exactly one of moon/sun should be visible"
        home.locator("#theme-toggle").click()
        home.wait_for_timeout(100)
        # After toggle they should swap
        assert moon.is_visible() != moon_vis or sun.is_visible() != sun_vis


class TestA11yControls:
    def test_high_contrast_toggle_exists(self, home: Page):
        btn = home.locator("#btn-contrast")
        expect(btn).to_be_visible()

    def test_high_contrast_toggle_has_label(self, home: Page):
        label = home.locator("#btn-contrast").get_attribute("aria-label")
        assert label and len(label) > 0

    def test_font_toggle_exists(self, home: Page):
        btn = home.locator("#btn-font")
        expect(btn).to_be_visible()

    def test_high_contrast_toggle_sets_aria_pressed(self, home: Page):
        btn = home.locator("#btn-contrast")
        initial = btn.get_attribute("aria-pressed")
        btn.click()
        home.wait_for_timeout(100)
        after = btn.get_attribute("aria-pressed")
        assert initial != after, "aria-pressed should flip on click"

    def test_font_toggle_sets_aria_pressed(self, home: Page):
        btn = home.locator("#btn-font")
        initial = btn.get_attribute("aria-pressed")
        btn.click()
        home.wait_for_timeout(100)
        after = btn.get_attribute("aria-pressed")
        assert initial != after


class TestAccessibilityStructure:
    def test_skip_link_exists(self, home: Page):
        skip = home.locator("a.skip-link")
        expect(skip).to_have_count(1)

    def test_skip_link_targets_main(self, home: Page):
        href = home.locator("a.skip-link").get_attribute("href")
        assert href == "#main"

    def test_main_landmark_exists(self, home: Page):
        expect(home.locator("main#main")).to_be_visible()

    def test_page_has_lang_attribute(self, home: Page):
        lang = home.evaluate("document.documentElement.lang")
        assert lang and len(lang) >= 2, f"Expected lang attribute, got: {lang!r}"
