"""Alert trigger rules - S032."""
from __future__ import annotations

import logging
from enum import Enum

from oykos.models.news_item import NewsItem
from oykos.models.taxonomy import DocumentType, TaxonomyTag

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    CRITICAL = "critical"  # AIFA safety alert, drug recall
    HIGH = "high"  # New guideline with immediate impact
    MEDIUM = "medium"  # Notable regulatory change


def evaluate_alert_triggers(item: NewsItem) -> AlertLevel | None:
    """Evaluate whether a news item triggers an immediate alert."""
    tags = {t.value for t in item.classification.taxonomy_tags}

    # Critical: drug safety + high urgency from authoritative source
    if (
        "drug_safety" in tags
        and item.scoring.subscores.urgency >= 4
        and item.source.reliability_tier >= 4
    ):
        logger.info("CRITICAL alert triggered: %s", item.content.title)
        return AlertLevel.CRITICAL

    # Critical: device safety alert
    if (
        "device_safety" in tags
        and item.scoring.subscores.urgency >= 4
        and item.content.document_type == DocumentType.SAFETY_COMMUNICATION
    ):
        return AlertLevel.CRITICAL

    # High: new guideline from major society with high clinical impact
    if (
        item.content.document_type in (DocumentType.GUIDELINE, DocumentType.CONSENSUS)
        and item.scoring.subscores.clinical_impact >= 4
        and item.source.reliability_tier >= 3
    ):
        return AlertLevel.HIGH

    # High: drug shortage affecting pediatrics
    if "drug_shortage" in tags and item.scoring.subscores.urgency >= 3:
        return AlertLevel.HIGH

    # Medium: regulatory change
    if (
        item.content.document_type == DocumentType.LEGAL_UPDATE
        and item.scoring.subscores.operational_impact >= 3
    ):
        return AlertLevel.MEDIUM

    # Medium: vaccination schedule change
    if "vaccinations" in tags and item.scoring.subscores.urgency >= 3:
        return AlertLevel.MEDIUM

    return None
