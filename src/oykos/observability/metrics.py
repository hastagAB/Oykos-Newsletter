"""Quality metrics - S037."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from oykos.models.news_item import Newsletter, NewsItem
from oykos.models.taxonomy import Geo

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    total_ingested: int = 0
    total_scored: int = 0
    total_selected: int = 0
    avg_score: float = 0.0
    italy_ratio: float = 0.0
    section_distribution: dict[str, int] = field(default_factory=dict)
    low_confidence_count: int = 0
    needs_review_count: int = 0
    alerts_triggered: int = 0
    issues: list[str] = field(default_factory=list)


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
        avg_score=round(avg_score, 2),
        alerts_triggered=alerts_count,
    )

    if newsletter:
        report.total_selected = len(newsletter.slots)
        report.italy_ratio = (
            newsletter.metrics.italy_count / len(newsletter.slots)
            if newsletter.slots
            else 0.0
        )
        report.section_distribution = newsletter.metrics.section_counts

        for slot in newsletter.slots:
            if slot.editorial.confidence.value == "low":
                report.low_confidence_count += 1
            if slot.editorial.review.needs_human_review:
                report.needs_review_count += 1

        # Quality checks
        if report.italy_ratio < 0.6:
            report.issues.append("Italy ratio below 60%")
        if report.low_confidence_count > 3:
            report.issues.append(f"{report.low_confidence_count} items with low confidence")
        if report.total_selected < 8:
            report.issues.append(f"Only {report.total_selected} items selected (target: 12)")

    logger.info(
        "Quality report: ingested=%d, scored=%d, selected=%d, avg=%.1f, issues=%d",
        report.total_ingested,
        report.total_scored,
        report.total_selected,
        report.avg_score,
        len(report.issues),
    )
    return report
