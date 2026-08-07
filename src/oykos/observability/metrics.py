"""Quality metrics - S037.

Implements the editorial KPIs of the blueprint (Section 10): coverage of every
core area, groundedness of claims, Italy/foreign ratio and the composition
constraints, so a run can be judged on editorial value rather than open rate.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from oykos.models.news_item import NewsItem, Newsletter
from oykos.models.taxonomy import Confidence, Geo, TaxonomyTag

logger = logging.getLogger(__name__)

# The Italy ratio is observed, not targeted. Since the 2026-08-07 editorial
# feedback every item competes on relevance to PLS practice, so a low Italian
# share means international evidence won slots, which is the intended outcome.
MAX_LOW_CONFIDENCE = 3

# Core areas that should be represented in every issue when material exists.
CORE_AREAS: dict[str, frozenset[TaxonomyTag]] = {
    "clinical": frozenset({
        TaxonomyTag.RESPIRATORY,
        TaxonomyTag.GASTROENTERITIS,
        TaxonomyTag.DERMATOLOGY,
        TaxonomyTag.ALLERGOLOGY,
        TaxonomyTag.NEURO_DEVELOPMENT,
        TaxonomyTag.EMERGENCIES_TRIAGE,
    }),
    "prevention": frozenset({
        TaxonomyTag.VACCINATIONS,
        TaxonomyTag.SURVEILLANCE,
        TaxonomyTag.ANTIBIOTIC_RESISTANCE,
    }),
    "medication": frozenset({
        TaxonomyTag.DRUG_SAFETY,
        TaxonomyTag.DRUG_AUTHORIZATION,
        TaxonomyTag.DRUG_SHORTAGE,
    }),
    "compliance": frozenset({
        TaxonomyTag.ACN_AGREEMENTS,
        TaxonomyTag.PRIVACY,
        TaxonomyTag.TELEMEDICINE,
    }),
    "device": frozenset({
        TaxonomyTag.RAPID_TESTS,
        TaxonomyTag.POCT_LAB,
        TaxonomyTag.FUNCTIONAL_DIAGNOSTICS,
        TaxonomyTag.SCREENING,
        TaxonomyTag.DEVICE_SAFETY,
    }),
    "training": frozenset({TaxonomyTag.CME_TRAINING, TaxonomyTag.CONGRESSES}),
}


@dataclass
class QualityReport:
    total_ingested: int = 0
    total_scored: int = 0
    total_gated_out: int = 0
    total_selected: int = 0
    avg_score: float = 0.0
    italy_ratio: float = 0.0
    section_distribution: dict[str, int] = field(default_factory=dict)
    covered_areas: list[str] = field(default_factory=list)
    missing_areas: list[str] = field(default_factory=list)
    groundedness: float = 0.0
    blocked_count: int = 0
    low_confidence_count: int = 0
    needs_review_count: int = 0
    alerts_triggered: int = 0
    issues: list[str] = field(default_factory=list)


def compute_groundedness(items: list[NewsItem]) -> float:
    """Share of editorial items whose claims are backed by extracted passages."""
    with_editorial = [i for i in items if i.editorial.summary]
    if not with_editorial:
        return 0.0
    grounded = sum(
        1
        for i in with_editorial
        if i.content.key_passages and i.editorial.citations and not i.editorial.unsupported_claims
    )
    return round(grounded / len(with_editorial), 3)


def compute_coverage(
    newsletter: Newsletter,
    candidates: list[NewsItem],
) -> tuple[list[str], list[str]]:
    """Which core areas the issue covers, and which are missing despite material."""
    published_ids = {slot.item_id for slot in newsletter.slots}
    published_tags: set[TaxonomyTag] = set()
    available_tags: set[TaxonomyTag] = set()

    for item in candidates:
        tags = set(item.classification.taxonomy_tags)
        available_tags |= tags
        if item.item_id in published_ids:
            published_tags |= tags

    covered = [area for area, tags in CORE_AREAS.items() if tags & published_tags]
    missing = [
        area
        for area, tags in CORE_AREAS.items()
        if area not in covered and tags & available_tags
    ]
    return covered, missing


def compute_quality_report(
    ingested: list[NewsItem],
    newsletter: Newsletter | None,
    alerts_count: int = 0,
) -> QualityReport:
    """Compute quality metrics for a pipeline run."""
    scored = [i for i in ingested if i.scoring.score_total > 0]
    avg_score = sum(i.scoring.score_total for i in scored) / len(scored) if scored else 0.0

    report = QualityReport(
        total_ingested=len(ingested),
        total_scored=len(scored),
        total_gated_out=sum(1 for i in ingested if i.gating.exclusions and not i.gating.passed),
        avg_score=round(avg_score, 2),
        groundedness=compute_groundedness(ingested),
        blocked_count=sum(1 for i in ingested if i.editorial.blocked),
        alerts_triggered=alerts_count,
    )

    if newsletter is None:
        _log(report)
        return report

    report.total_selected = len(newsletter.slots)
    report.section_distribution = newsletter.metrics.section_counts
    report.italy_ratio = (
        round(newsletter.metrics.italy_count / len(newsletter.slots), 3)
        if newsletter.slots
        else 0.0
    )
    report.covered_areas, report.missing_areas = compute_coverage(newsletter, ingested)

    for slot in newsletter.slots:
        if slot.editorial.confidence is Confidence.LOW:
            report.low_confidence_count += 1
        if slot.editorial.review.needs_human_review:
            report.needs_review_count += 1

    if report.low_confidence_count > MAX_LOW_CONFIDENCE:
        report.issues.append(f"{report.low_confidence_count} items with low confidence")
    # A thin week is a correct outcome, not a defect: the guidelines put recency
    # above filling the layout. Only an empty issue is worth flagging.
    if report.total_selected == 0:
        report.issues.append("No item published this week cleared the gates")
    if report.missing_areas:
        report.issues.append(f"Core areas missing: {', '.join(report.missing_areas)}")
    if report.blocked_count:
        report.issues.append(f"{report.blocked_count} items blocked for ungrounded claims")

    _log(report)
    return report


def _log(report: QualityReport) -> None:
    logger.info(
        "Quality report: ingested=%d scored=%d selected=%d avg=%.1f "
        "italy=%.0f%% grounded=%.0f%% issues=%d",
        report.total_ingested,
        report.total_scored,
        report.total_selected,
        report.avg_score,
        report.italy_ratio * 100,
        report.groundedness * 100,
        len(report.issues),
    )


def italy_geo_count(items: list[NewsItem]) -> int:
    """Helper for reporting: how many items are Italian."""
    return sum(1 for i in items if i.classification.geo is Geo.IT)
