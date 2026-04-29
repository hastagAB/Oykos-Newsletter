"""Tests for newsletter composer - S022."""
from __future__ import annotations

from uuid import uuid4

from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import Geo, Section, TaxonomyTag
from oykos.newsletter.composer import compose_newsletter


def _make_item(
    score: float = 70.0,
    geo: Geo = Geo.IT,
    tags: list[TaxonomyTag] | None = None,
    source_trust: int = 4,
) -> NewsItem:
    return NewsItem(
        item_id=uuid4(),
        source=SourceRef(key="test", name="Test", source_type="rss", country="IT", reliability_tier=source_trust),
        content=ContentBlock(title=f"Article {score}", canonical_url=f"https://example.com/{uuid4()}"),
        classification=Classification(geo=geo, taxonomy_tags=tags or []),
        scoring=ScoringBlock(
            score_total=score,
            subscores=Subscores(source_trust=source_trust),
        ),
        editorial=EditorialBlock(headline_operational=f"Headline {score}"),
    )


def test_compose_basic() -> None:
    items = [_make_item(90 - i * 5) for i in range(15)]
    nl = compose_newsletter(items, "2026-W18")
    assert nl.week == "2026-W18"
    assert len(nl.slots) <= 12
    assert nl.metrics.italy_count + nl.metrics.foreign_count == len(nl.slots)


def test_compose_empty_candidates() -> None:
    nl = compose_newsletter([], "2026-W18")
    assert len(nl.slots) == 0


def test_compose_preserves_section_order() -> None:
    items = [_make_item(90 - i * 5) for i in range(10)]
    nl = compose_newsletter(items, "2026-W18")
    # Slots should have positions starting from 1
    for i, slot in enumerate(nl.slots):
        assert slot.position == i + 1
