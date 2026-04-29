"""Tests for ranker with composition constraints - S016."""
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
from oykos.processing.ranker import assign_section, rank_and_select, MAX_TOTAL


def _make_item(
    score: float = 50.0,
    geo: Geo = Geo.IT,
    tags: list[TaxonomyTag] | None = None,
    urgency: int = 2,
    source_trust: int = 4,
    device: bool = False,
) -> NewsItem:
    return NewsItem(
        item_id=uuid4(),
        source=SourceRef(key="test", name="Test", source_type="rss", country="IT", reliability_tier=source_trust),
        content=ContentBlock(title=f"Article {score}", canonical_url=f"https://example.com/{uuid4()}"),
        classification=Classification(
            geo=geo,
            taxonomy_tags=tags or [],
            device_related=device,
        ),
        scoring=ScoringBlock(
            score_total=score,
            subscores=Subscores(urgency=urgency, source_trust=source_trust),
        ),
        editorial=EditorialBlock(headline_operational="Test headline"),
    )


def test_assign_section_top_priority_urgency() -> None:
    item = _make_item(urgency=4)
    assert assign_section(item) == Section.TOP_PRIORITY


def test_assign_section_drug_safety() -> None:
    item = _make_item(tags=[TaxonomyTag.DRUG_SAFETY])
    assert assign_section(item) == Section.TOP_PRIORITY


def test_assign_section_cme() -> None:
    item = _make_item(tags=[TaxonomyTag.CME_TRAINING])
    assert assign_section(item) == Section.CME


def test_assign_section_regulatory() -> None:
    item = _make_item(tags=[TaxonomyTag.ACN_AGREEMENTS])
    assert assign_section(item) == Section.REGULATORY


def test_assign_section_device() -> None:
    item = _make_item(device=True)
    assert assign_section(item) == Section.DEVICE


def test_assign_section_clinical_default() -> None:
    item = _make_item(tags=[TaxonomyTag.RESPIRATORY])
    assert assign_section(item) == Section.CLINICAL


def test_rank_and_select_respects_max() -> None:
    items = [_make_item(score=90 - i) for i in range(20)]
    selected = rank_and_select(items)
    assert len(selected) <= MAX_TOTAL


def test_rank_and_select_geo_constraint() -> None:
    # 10 Italian, 10 foreign
    items = [_make_item(score=90 - i, geo=Geo.IT) for i in range(10)]
    items += [_make_item(score=85 - i, geo=Geo.EU) for i in range(10)]
    selected = rank_and_select(items)

    italy = sum(1 for item, _ in selected if item.classification.geo == Geo.IT)
    foreign = sum(1 for item, _ in selected if item.classification.geo != Geo.IT)
    assert italy <= 8
    assert foreign <= 4


def test_rank_and_select_low_trust_excluded_from_top5() -> None:
    items = [_make_item(score=95, source_trust=1)]  # Low trust, high score
    items += [_make_item(score=80 - i, source_trust=4) for i in range(11)]
    selected = rank_and_select(items)

    # Low-trust item should not be in first 5 positions
    for item, _ in selected[:5]:
        assert item.scoring.subscores.source_trust > 2
