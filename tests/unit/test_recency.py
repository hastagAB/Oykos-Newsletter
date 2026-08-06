"""The same-week rule from the editorial guidelines (v1.0, 2026-08-05).

"Every item must have been published during the same week in which the
newsletter is sent. Recency takes priority over filling a predetermined number
of sections."
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from oykos.models.news_item import ContentBlock, NewsItem, SourceRef
from oykos.processing.recency import filter_to_week, iso_week_key, published_in_week

WEEK = "2026-W32"


def _item(published: datetime | None) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key="src", name="Fonte", source_type="rss", country="IT", reliability_tier=4,
        ),
        content=ContentBlock(
            title="Titolo",
            canonical_url="https://esempio.it/x",
            published_at=published,
        ),
    )


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (datetime(2026, 8, 4, tzinfo=UTC), "2026-W32"),
        (datetime(2026, 8, 3, tzinfo=UTC), "2026-W32"),
        (datetime(2026, 8, 9, tzinfo=UTC), "2026-W32"),
        (datetime(2026, 8, 10, tzinfo=UTC), "2026-W33"),
        (datetime(2026, 1, 1, tzinfo=UTC), "2026-W01"),
    ],
)
def test_iso_week_key(moment: datetime, expected: str) -> None:
    assert iso_week_key(moment) == expected


def test_item_from_the_issue_week_is_kept() -> None:
    assert published_in_week(_item(datetime(2026, 8, 5, tzinfo=UTC)), WEEK)


def test_item_from_last_week_is_rejected() -> None:
    assert not published_in_week(_item(datetime(2026, 7, 30, tzinfo=UTC)), WEEK)


def test_item_from_2016_is_rejected() -> None:
    assert not published_in_week(_item(datetime(2016, 8, 1, tzinfo=UTC)), WEEK)


def test_undated_item_is_rejected() -> None:
    """The guidelines require every publication date to be verified before inclusion."""
    assert not published_in_week(_item(None), WEEK)


def test_a_thin_week_yields_a_short_issue_rather_than_stale_filler() -> None:
    candidates = [
        _item(datetime(2026, 8, 5, tzinfo=UTC)),
        _item(datetime(2026, 7, 1, tzinfo=UTC)),
        _item(None),
        _item(datetime(2016, 8, 1, tzinfo=UTC)),
    ]

    kept = filter_to_week(candidates, WEEK)

    assert len(kept) == 1
