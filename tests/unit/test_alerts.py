"""Tests for alert triggers - S032."""
from __future__ import annotations

from uuid import uuid4

from oykos.alerts.triggers import AlertLevel, evaluate_alert_triggers
from oykos.models.news_item import (
    Classification,
    ContentBlock,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import DocumentType, Geo, TaxonomyTag


def _make_item(
    tags: list[TaxonomyTag] | None = None,
    urgency: int = 2,
    clinical_impact: int = 2,
    operational_impact: int = 2,
    source_trust: int = 4,
    doc_type: DocumentType = DocumentType.NEWS,
) -> NewsItem:
    return NewsItem(
        item_id=uuid4(),
        source=SourceRef(key="test", name="Test", source_type="rss", country="IT", reliability_tier=source_trust),
        content=ContentBlock(
            title="Test",
            canonical_url=f"https://example.com/{uuid4()}",
            document_type=doc_type,
        ),
        classification=Classification(
            geo=Geo.IT,
            taxonomy_tags=tags or [],
        ),
        scoring=ScoringBlock(
            subscores=Subscores(
                urgency=urgency,
                clinical_impact=clinical_impact,
                operational_impact=operational_impact,
                source_trust=source_trust,
            ),
        ),
    )


def test_critical_drug_safety() -> None:
    item = _make_item(tags=[TaxonomyTag.DRUG_SAFETY], urgency=4, source_trust=5)
    assert evaluate_alert_triggers(item) == AlertLevel.CRITICAL


def test_critical_device_safety() -> None:
    item = _make_item(
        tags=[TaxonomyTag.DEVICE_SAFETY],
        urgency=4,
        doc_type=DocumentType.SAFETY_COMMUNICATION,
    )
    assert evaluate_alert_triggers(item) == AlertLevel.CRITICAL


def test_high_new_guideline() -> None:
    item = _make_item(
        doc_type=DocumentType.GUIDELINE,
        clinical_impact=4,
        source_trust=4,
    )
    assert evaluate_alert_triggers(item) == AlertLevel.HIGH


def test_high_drug_shortage() -> None:
    item = _make_item(tags=[TaxonomyTag.DRUG_SHORTAGE], urgency=3)
    assert evaluate_alert_triggers(item) == AlertLevel.HIGH


def test_medium_legal_update() -> None:
    item = _make_item(doc_type=DocumentType.LEGAL_UPDATE, operational_impact=3)
    assert evaluate_alert_triggers(item) == AlertLevel.MEDIUM


def test_medium_vaccination() -> None:
    item = _make_item(tags=[TaxonomyTag.VACCINATIONS], urgency=3)
    assert evaluate_alert_triggers(item) == AlertLevel.MEDIUM


def test_no_alert_routine() -> None:
    item = _make_item()
    assert evaluate_alert_triggers(item) is None


def test_no_alert_low_urgency_drug_safety() -> None:
    item = _make_item(tags=[TaxonomyTag.DRUG_SAFETY], urgency=2, source_trust=3)
    assert evaluate_alert_triggers(item) is None
