"""Alert trigger rules - S032.

The blueprint allows trigger alerts only for "hard" and rare events, at most 1-2
per month, because over-notification causes alert fatigue in primary care and
destroys the value of the weekly digest. Exactly four categories qualify:

1. AIFA safety communications / Important Information Notes
2. Ministry or ISS updates on viral circulation with outpatient impact
3. Safety alerts on outpatient devices and IVDs (FSN / FSCA)
4. Official ACN changes, agreements and operating rules
"""
from __future__ import annotations

import logging
from enum import Enum

from oykos.models.news_item import NewsItem
from oykos.models.taxonomy import DocumentType, TaxonomyTag

logger = logging.getLogger(__name__)

# A trigger only fires on an authoritative source.
MIN_ALERT_RELIABILITY = 4
HIGH_URGENCY = 4
STRONG_IMPACT = 4

# Source keys that can raise each category of alert.
AIFA_SOURCE_KEYS = frozenset({"aifa_safety", "ema_news"})
SURVEILLANCE_SOURCE_KEYS = frozenset({
    "respivirnet",
    "iss_epicentro",
    "min_salute_pnpv",
    "ecdc_cdtr",
})
DEVICE_SAFETY_SOURCE_KEYS = frozenset({
    "min_salute_fsn",
    "min_salute_dm_db",
    "min_salute_segnalazioni",
})
ACN_SOURCE_KEYS = frozenset({"sisac_acn"})


class AlertLevel(str, Enum):
    CRITICAL = "critical"  # AIFA safety alert, device FSN/FSCA
    HIGH = "high"  # Epidemic signal with outpatient impact, ACN change
    MEDIUM = "medium"  # Reserved: never emitted by the blueprint rules


class AlertCategory(str, Enum):
    DRUG_SAFETY = "drug_safety"
    DEVICE_SAFETY = "device_safety"
    EPIDEMIC_SURVEILLANCE = "epidemic_surveillance"
    ACN_CHANGE = "acn_change"


CATEGORY_LEVEL: dict[AlertCategory, AlertLevel] = {
    AlertCategory.DRUG_SAFETY: AlertLevel.CRITICAL,
    AlertCategory.DEVICE_SAFETY: AlertLevel.CRITICAL,
    AlertCategory.EPIDEMIC_SURVEILLANCE: AlertLevel.HIGH,
    AlertCategory.ACN_CHANGE: AlertLevel.HIGH,
}


def classify_alert(item: NewsItem) -> AlertCategory | None:
    """Return the alert category for an item, or None if it is not a hard event."""
    if item.source.reliability_tier < MIN_ALERT_RELIABILITY:
        return None

    tags = set(item.classification.taxonomy_tags)
    subscores = item.scoring.subscores

    # 1. AIFA / EMA drug safety communication.
    if (
        TaxonomyTag.DRUG_SAFETY in tags
        and item.source.key in AIFA_SOURCE_KEYS
        and (
            item.content.document_type is DocumentType.SAFETY_COMMUNICATION
            or subscores.urgency >= HIGH_URGENCY
        )
    ):
        return AlertCategory.DRUG_SAFETY

    # 2. Device / IVD field safety notice.
    if (
        item.source.key in DEVICE_SAFETY_SOURCE_KEYS
        or (TaxonomyTag.DEVICE_SAFETY in tags and item.classification.device_related)
    ) and item.content.document_type is DocumentType.SAFETY_COMMUNICATION:
        return AlertCategory.DEVICE_SAFETY

    # 3. Surveillance signal with real outpatient impact.
    if (
        item.source.key in SURVEILLANCE_SOURCE_KEYS
        and TaxonomyTag.SURVEILLANCE in tags
        and subscores.urgency >= HIGH_URGENCY
        and subscores.clinical_impact >= STRONG_IMPACT
    ):
        return AlertCategory.EPIDEMIC_SURVEILLANCE

    # 4. Official ACN / agreement change.
    if (
        TaxonomyTag.ACN_AGREEMENTS in tags
        and item.source.key in ACN_SOURCE_KEYS
        and item.content.document_type is DocumentType.LEGAL_UPDATE
        and subscores.operational_impact >= STRONG_IMPACT
    ):
        return AlertCategory.ACN_CHANGE

    return None


def evaluate_alert_triggers(item: NewsItem) -> AlertLevel | None:
    """Evaluate whether a news item triggers an immediate alert."""
    category = classify_alert(item)
    if category is None:
        return None
    level = CATEGORY_LEVEL[category]
    logger.info(
        "%s alert triggered [%s]: %s",
        level.value.upper(),
        category.value,
        item.content.title,
    )
    return level
