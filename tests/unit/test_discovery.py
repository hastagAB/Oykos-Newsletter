"""Tests for event listing discovery.

Discovery decides which page the extractor reads. Getting it wrong is expensive
in both directions: an archive page advertises expired events, and a missed
listing means a society disappears from the newsletter silently.
"""
from __future__ import annotations

import pytest

from oykos.events.discovery import (
    candidates_from_html,
    candidates_from_sitemap,
    count_dates,
    is_archive_url,
)

HOME = "https://www.fimp.pro"
DOMAIN = "www.fimp.pro"


def test_italian_prose_dates_are_counted() -> None:
    assert count_dates("Il convegno si terra' il 4 settembre e il 5 ottobre") == 2


def test_numeric_and_iso_dates_are_counted() -> None:
    assert count_dates("04/09/2026 e 2026-10-05") == 2


def test_text_without_dates_counts_zero() -> None:
    assert count_dates("Chi siamo, contatti, area riservata") == 0


@pytest.mark.parametrize(
    "url",
    [
        "https://www.fimp.pro/eventi/eventi-passati",
        "https://x.it/archivio-congressi",
        "https://x.it/edizioni-precedenti",
        "https://x.it/eventi/scaduti",
    ],
)
def test_archive_pages_are_refused(url: str) -> None:
    """A past-events list has more dates than the upcoming one, so a naive date
    count picks it. Observed on fimp.pro."""
    assert is_archive_url(url) is True


def test_upcoming_page_is_not_treated_as_an_archive() -> None:
    assert is_archive_url("https://www.fimp.pro/eventi/prossimi-eventi") is False


def test_event_links_are_found_in_html() -> None:
    html = """
    <a href="/eventi/prossimi-eventi">Prossimi eventi</a>
    <a href="/chi-siamo">Chi siamo</a>
    <a href="/formazione/corsi-ecm">Corsi ECM</a>
    """

    found = candidates_from_html(html, HOME, DOMAIN)

    assert f"{HOME}/eventi/prossimi-eventi" in found
    assert f"{HOME}/formazione/corsi-ecm" in found
    assert f"{HOME}/chi-siamo" not in found


def test_archive_links_are_not_offered_as_candidates() -> None:
    html = '<a href="/eventi/eventi-passati">Eventi passati</a>'

    assert candidates_from_html(html, HOME, DOMAIN) == []


def test_english_section_labels_are_recognised() -> None:
    """Several Italian societies and PCOs label the section in English."""
    html = '<a href="/congress-calendar">Congress Calendar</a>'

    assert candidates_from_html(html, HOME, DOMAIN) == [f"{HOME}/congress-calendar"]


def test_external_links_are_ignored() -> None:
    html = '<a href="https://altro.it/eventi">Eventi altrove</a>'

    assert candidates_from_html(html, HOME, DOMAIN) == []


def test_non_http_links_are_ignored() -> None:
    html = '<a href="mailto:info@fimp.pro">Eventi</a><a href="#eventi">Eventi</a>'

    assert candidates_from_html(html, HOME, DOMAIN) == []


def test_sitemap_yields_event_urls_only() -> None:
    xml = """<urlset>
      <url><loc>https://www.fimp.pro/eventi/prossimi-eventi</loc></url>
      <url><loc>https://www.fimp.pro/privacy</loc></url>
      <url><loc>https://www.fimp.pro/eventi/eventi-passati</loc></url>
    </urlset>"""

    found = candidates_from_sitemap(xml, DOMAIN)

    assert found == ["https://www.fimp.pro/eventi/prossimi-eventi"]
