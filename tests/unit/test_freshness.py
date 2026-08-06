"""Freshness and access checks at ingestion.

Both cases here came from a pediatrician reviewing a live issue: a 2016
publication presented as this week's news, and a link into a members-only area.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from oykos.ingestion.orchestrator import MAX_ITEM_AGE_DAYS
from oykos.ingestion.scraper import extract_published_at, is_paywalled


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://sip.it/2016/08/01/nuove-linee-guida-epilessia", datetime(2016, 8, 1, tzinfo=UTC)),
        ("https://sip.it/2026/08/04/xvi-congresso", datetime(2026, 8, 4, tzinfo=UTC)),
        ("https://esempio.it/2026/03/", datetime(2026, 3, 1, tzinfo=UTC)),
    ],
)
def test_publication_date_is_recovered_from_the_permalink(
    url: str, expected: datetime,
) -> None:
    assert extract_published_at("", url) == expected


def test_publication_date_falls_back_to_page_metadata() -> None:
    html = '<meta property="article:published_time" content="2026-07-15T09:30:00Z">'
    assert extract_published_at(html, "https://esempio.it/senza-data") == datetime(
        2026, 7, 15, 9, 30, tzinfo=UTC,
    )


def test_json_ld_date_is_read() -> None:
    html = '<script type="application/ld+json">{"datePublished":"2026-07-20T08:00:00Z"}</script>'
    assert extract_published_at(html, "https://esempio.it/x") == datetime(
        2026, 7, 20, 8, 0, tzinfo=UTC,
    )


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>Pubblicato il 5 agosto 2026</p>", datetime(2026, 8, 5, tzinfo=UTC)),
        ("<p>12 dicembre 2025</p>", datetime(2025, 12, 12, tzinfo=UTC)),
        ("<span>1 Gennaio 2026</span>", datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_italian_prose_dates_are_read(html: str, expected: datetime) -> None:
    """Half our Italian sources print the date only in prose."""
    assert extract_published_at(html, "https://esempio.it/x") == expected


def test_numeric_dates_are_read_day_first() -> None:
    """Italian convention is day/month/year."""
    assert extract_published_at("<p>05/08/2026</p>", "https://esempio.it/x") == datetime(
        2026, 8, 5, tzinfo=UTC,
    )


def test_future_dates_are_refused() -> None:
    """NICE marks consultation closing dates in <time>; those are not publication dates."""
    future = datetime.now(UTC) + timedelta(days=30)
    html = f'<time datetime="{future.isoformat()}">'

    assert extract_published_at(html, "https://esempio.it/x") is None


def test_structured_metadata_wins_over_prose() -> None:
    html = (
        '<meta property="article:published_time" content="2026-07-15T09:30:00Z">'
        "<p>Aggiornato il 2 agosto 2026</p>"
    )
    assert extract_published_at(html, "https://esempio.it/x") == datetime(
        2026, 7, 15, 9, 30, tzinfo=UTC,
    )


def test_undated_pages_are_not_guessed() -> None:
    """Many institutional pages carry no date; refusing them all would starve the issue."""
    assert extract_published_at("<html><body>niente</body></html>", "https://esempio.it/x") is None


def test_a_2016_publication_falls_outside_the_freshness_window() -> None:
    cutoff = datetime.now(UTC) - timedelta(days=MAX_ITEM_AGE_DAYS)
    stale = extract_published_at("", "https://sip.it/2016/08/01/linee-guida")

    assert stale is not None
    assert stale < cutoff


@pytest.mark.parametrize(
    "text",
    [
        "L'accesso a questo contenuto è riservato esclusivamente ai soci SICuPP.",
        "Contenuto riservato. Effettua il login per continuare.",
        "This article is for members only.",
    ],
)
def test_login_walls_are_recognised(text: str) -> None:
    assert is_paywalled(text)


def test_real_articles_are_not_mistaken_for_login_walls() -> None:
    text = (
        "La saturimetria domiciliare non è raccomandata di routine nel lattante con "
        "bronchiolite lieve gestito a domicilio, secondo le nuove raccomandazioni."
    )
    assert not is_paywalled(text)
