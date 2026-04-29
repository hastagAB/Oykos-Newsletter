"""Tests for quality metrics - S037."""
from __future__ import annotations

from uuid import uuid4

from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    IssueMetrics,
    Newsletter,
    NewsItem,
    NewsletterSlot,
    ReviewStatus,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import Confidence, Geo, IssueStatus, Section
from oykos.observability.metrics import compute_quality_report


def _make_item(score: float = 60.0) -> NewsItem:
    return NewsItem(
        source=SourceRef(key="test", name="Test", source_type="rss", country="IT", reliability_tier=4),
        content=ContentBlock(title="Test", canonical_url=f"https://example.com/{uuid4()}"),
        scoring=ScoringBlock(score_total=score),
    )


def _make_newsletter(n_slots: int = 10, italy: int = 7) -> Newsletter:
    slots = []
    for i in range(n_slots):
        slots.append(NewsletterSlot(
            position=i + 1,
            section=Section.CLINICAL,
            item_id=uuid4(),
            editorial=EditorialBlock(
                headline_operational=f"Item {i}",
                confidence=Confidence.HIGH if i < 7 else Confidence.LOW,
                review=ReviewStatus(needs_human_review=i >= 8),
            ),
        ))
    return Newsletter(
        week="2026-W18",
        status=IssueStatus.DRAFT,
        slots=slots,
        metrics=IssueMetrics(
            italy_count=italy,
            foreign_count=n_slots - italy,
            section_counts={"clinical": n_slots},
        ),
    )


def test_report_basic() -> None:
    items = [_make_item(60), _make_item(80), _make_item(0)]
    nl = _make_newsletter()
    report = compute_quality_report(items, nl)
    assert report.total_ingested == 3
    assert report.total_scored == 2
    assert report.avg_score == 70.0


def test_report_italy_ratio() -> None:
    items = [_make_item()]
    nl = _make_newsletter(n_slots=10, italy=7)
    report = compute_quality_report(items, nl)
    assert report.italy_ratio == 0.7


def test_report_flags_low_italy() -> None:
    items = [_make_item()]
    nl = _make_newsletter(n_slots=10, italy=5)
    report = compute_quality_report(items, nl)
    assert any("Italy ratio" in issue for issue in report.issues)


def test_report_no_newsletter() -> None:
    items = [_make_item(50)]
    report = compute_quality_report(items, None)
    assert report.total_selected == 0
    assert report.italy_ratio == 0.0


def test_report_counts_low_confidence() -> None:
    items = [_make_item()]
    nl = _make_newsletter(n_slots=10, italy=7)
    report = compute_quality_report(items, nl)
    assert report.low_confidence_count == 3  # Items 7, 8, 9 have LOW confidence
