"""Tests for oykos.models.taxonomy - S003."""
from __future__ import annotations

from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    Geo,
    IssueStatus,
    Section,
    Setting,
    SourceType,
    TaxonomyTag,
    Tier,
)


def test_tier_values() -> None:
    assert Tier.TIER_1_ITALY.value == "tier_1_italy"
    assert Tier.TIER_2_EUROPE.value == "tier_2_europe"
    assert Tier.TIER_3_GLOBAL.value == "tier_3_global"
    assert Tier.RADAR.value == "radar"


def test_geo_values() -> None:
    assert Geo.IT.value == "IT"
    assert Geo.EU.value == "EU"
    assert Geo.GLOBAL.value == "GLOBAL"


def test_taxonomy_tag_clinical_territory() -> None:
    clinical = [
        TaxonomyTag.RESPIRATORY,
        TaxonomyTag.GASTROENTERITIS,
        TaxonomyTag.DERMATOLOGY,
        TaxonomyTag.ALLERGOLOGY,
        TaxonomyTag.NEURO_DEVELOPMENT,
        TaxonomyTag.EMERGENCIES_TRIAGE,
    ]
    assert len(clinical) == 6
    for tag in clinical:
        assert isinstance(tag, TaxonomyTag)


def test_taxonomy_tag_all_categories_present() -> None:
    all_tags = list(TaxonomyTag)
    assert len(all_tags) == 22


def test_section_values() -> None:
    assert Section.TOP_PRIORITY.value == "top_priority"
    assert Section.CLINICAL.value == "clinical"
    assert Section.REGULATORY.value == "regulatory"
    assert Section.DEVICE.value == "device"
    assert Section.CME.value == "cme"


def test_document_type_values() -> None:
    assert DocumentType.SAFETY_COMMUNICATION.value == "safety_communication"
    assert DocumentType.GUIDELINE.value == "guideline"
    assert len(list(DocumentType)) == 8


def test_confidence_values() -> None:
    assert Confidence.HIGH.value == "high"
    assert Confidence.MEDIUM.value == "medium"
    assert Confidence.LOW.value == "low"


def test_setting_values() -> None:
    assert Setting.TERRITORY.value == "territory"
    assert Setting.HOSPITAL.value == "hospital"
    assert Setting.MIXED.value == "mixed"


def test_source_type_values() -> None:
    assert SourceType.RSS.value == "rss"
    assert SourceType.SCRAPE.value == "scrape"
    assert SourceType.API.value == "api"
    assert SourceType.PDF.value == "pdf"


def test_issue_status_values() -> None:
    assert IssueStatus.DRAFT.value == "draft"
    assert IssueStatus.IN_REVIEW.value == "in_review"
    assert IssueStatus.APPROVED.value == "approved"
    assert IssueStatus.SENT.value == "sent"


def test_tier_is_italian() -> None:
    assert Tier.TIER_1_ITALY.value.startswith("tier_1")
    assert not Tier.TIER_2_EUROPE.value.startswith("tier_1")
