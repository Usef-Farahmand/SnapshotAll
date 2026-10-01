"""Browser tests for full-page capture of pages with fixed / sticky elements.

Needs Playwright with a browser. Set SNAPSHOTALL_TEST_CHROMIUM to use a specific Chromium binary;
otherwise Playwright's own browser is used. Tests are skipped when no browser can be launched.
"""
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from snapshot_all import SCROLL_JS, TIDY_JS  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as pw:
        exe = os.environ.get("SNAPSHOTALL_TEST_CHROMIUM")
        try:
            if exe:
                b = pw.chromium.launch(executable_path=exe,
                                       args=["--no-sandbox", "--disable-setuid-sandbox", "--single-process", "--no-zygote"])
            else:
                b = pw.chromium.launch()
        except Exception as e:  # no browser installed
            pytest.skip(f"no browser available: {e}")
        yield b
        b.close()


def prepared_page(browser, name, viewport=(1440, 900)):
    page = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}).new_page()
    page.goto((FIXTURES / name).as_uri())
    page.wait_for_timeout(300)
    page.evaluate(SCROLL_JS)
    return page


def test_page_is_back_at_top_even_with_smooth_scroll(browser):
    page = prepared_page(browser, "lazy_smooth_scroll.html")
    assert page.evaluate("window.scrollY") == 0


def test_lazy_content_is_fully_loaded(browser):
    page = prepared_page(browser, "lazy_smooth_scroll.html")
    assert page.evaluate("document.querySelectorAll('section').length") == 7


def test_fixed_footer_moves_to_the_end_of_the_page(browser):
    page = prepared_page(browser, "floating_bars.html")
    page.evaluate(TIDY_JS)
    bottom = page.evaluate("""() => {
        const r = document.getElementById('site-footer').getBoundingClientRect();
        return [r.bottom + window.scrollY, document.documentElement.scrollHeight];
    }""")
    assert abs(bottom[0] - bottom[1]) <= 2


def test_cookie_banner_is_hidden_and_sticky_bar_is_in_flow(browser):
    page = prepared_page(browser, "floating_bars.html")
    result = page.evaluate(TIDY_JS)
    assert result == {"moved": 1, "hidden": 1, "unstuck": 1}
    assert page.evaluate("getComputedStyle(document.querySelector('.cookie')).visibility") == "hidden"
    assert page.evaluate("getComputedStyle(document.querySelector('.stickybar')).position") == "relative"


def test_fixed_header_and_full_height_sidebar_are_left_alone(browser):
    page = prepared_page(browser, "floating_bars.html")
    page.evaluate(TIDY_JS)
    assert page.evaluate("getComputedStyle(document.querySelector('header')).position") == "fixed"
    page = prepared_page(browser, "lazy_smooth_scroll.html")
    page.evaluate(TIDY_JS)
    assert page.evaluate("getComputedStyle(document.querySelector('nav')).visibility") == "visible"
    assert page.evaluate("getComputedStyle(document.querySelector('.btt')).visibility") == "hidden"
