"""Recency rules for issue composition.

The editorial guidelines (v1.0, 2026-08-05) make this an absolute constraint:
every item must have been published in the same ISO week the issue is sent, and
the publication date must be verifiable. Recency outranks filling the layout -
an issue with one item is correct if only one thing was published that week.
"""
from __future__ import annotations

from datetime import date, datetime

from oykos.models.news_item import NewsItem


def iso_week_key(moment: date | datetime) -> str:
    """The ``YYYY-Www`` key an issue is filed under."""
    year, week, _ = moment.isocalendar()
    return f"{year}-W{week:02d}"


def published_in_week(item: NewsItem, week: str) -> bool:
    """True only when the item carries a verifiable date inside ``week``.

    An unknown date is a failure, not a pass: the guidelines require the date of
    every source to be verified before inclusion.
    """
    published = item.content.published_at
    if published is None:
        return False
    return iso_week_key(published) == week


def filter_to_week(items: list[NewsItem], week: str) -> list[NewsItem]:
    """Keep only the items published during ``week``."""
    return [item for item in items if published_in_week(item, week)]
