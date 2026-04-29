"""Tests for NewsItem data model - S004."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    Newsletter,
    NewsletterSlot,
    ReviewDecision,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    Geo,
    IssueStatus,
    Section,
    Setting,
    TaxonomyTag,
)


def _make_source_ref() -> SourceRef:
    return SourceRef(
        key="aifa_safety",
        name="AIFA",
        source_type="scrape",
        country="IT",
        reliability_tier=5,
    )


def _make_content() -> ContentBlock:
    return ContentBlock(
        title="Test Article",
        canonical_url="https://example.com/article",
        published_at=datetime(2026, 4, 1),
    )


def test_news_item_creation() -> None:
    item = NewsItem(source=_make_source_ref(), content=_make_content())
    assert isinstance(item.item_id, UUID)
    assert item.content.title == "Test Article"
    assert item.scoring.score_total == 0.0
    assert item.classification.geo == Geo.IT


def test_news_item_full() -> None:
    item = NewsItem(
        source=_make_source_ref(),
        content=_make_content(),
        classification=Classification(
            geo=Geo.IT,
            taxonomy_tags=[TaxonomyTag.DRUG_SAFETY],
            setting=Setting.TERRITORY,
            pls_relevance=0.9,
            device_related=False,
        ),
        scoring=ScoringBlock(
            score_total=85.0,
            subscores=Subscores(
                pls_relevance=5,
                clinical_impact=4,
                operational_impact=3,
                source_trust=5,
                novelty=4,
                actionability=4,
                urgency=3,
            ),
        ),
    )
    assert item.scoring.score_total == 85.0
    assert item.scoring.subscores.pls_relevance == 5


def test_subscores_range_validation() -> None:
    with pytest.raises(ValidationError):
        Subscores(pls_relevance=6)
    with pytest.raises(ValidationError):
        Subscores(pls_relevance=-1)


def test_scoring_block_range() -> None:
    with pytest.raises(ValidationError):
        ScoringBlock(score_total=101.0)
    with pytest.raises(ValidationError):
        ScoringBlock(score_total=-1.0)


def test_classification_pls_relevance_range() -> None:
    with pytest.raises(ValidationError):
        Classification(pls_relevance=1.5)


def test_editorial_block_defaults() -> None:
    eb = EditorialBlock()
    assert eb.confidence == Confidence.LOW
    assert eb.review.needs_human_review is True
    assert eb.review.review_status == "pending"


def test_newsletter_creation() -> None:
    nl = Newsletter(week="2026-W17")
    assert nl.status == IssueStatus.DRAFT
    assert nl.slots == []
    assert isinstance(nl.issue_id, UUID)


def test_newsletter_slot_position_range() -> None:
    with pytest.raises(ValidationError):
        NewsletterSlot(
            position=0,
            section=Section.TOP_PRIORITY,
            item_id=NewsItem(source=_make_source_ref(), content=_make_content()).item_id,
            editorial=EditorialBlock(),
        )


def test_review_decision() -> None:
    from uuid import uuid4

    rd = ReviewDecision(
        item_id=uuid4(),
        issue_id=uuid4(),
        reviewer_role="medical_editor",
        status="approved",
    )
    assert rd.status == "approved"
    assert rd.edits is None


def test_content_block_document_type() -> None:
    cb = ContentBlock(
        title="Test",
        canonical_url="https://example.com",
        document_type=DocumentType.SAFETY_COMMUNICATION,
    )
    assert cb.document_type == DocumentType.SAFETY_COMMUNICATION


def test_source_ref_reliability_range() -> None:
    with pytest.raises(ValidationError):
        SourceRef(key="x", name="X", source_type="rss", country="IT", reliability_tier=6)
