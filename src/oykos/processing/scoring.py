"""Scoring and noise penalties - docs/scoring.md.

Seven weighted dimensions produce a 0-100 raw score. Foreign items are then
discounted by how well they transfer to Italian practice, and noisy items lose
points. The subscores themselves come from the triage model.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from oykos.models.news_item import NewsItem, ScoringBlock, Subscores
from oykos.models.taxonomy import DocumentType, Geo, Penalty

WEIGHTS = {
    "pls_relevance": 0.22,
    "clinical_impact": 0.18,
    "operational_impact": 0.15,
    "source_trust": 0.15,
    "novelty": 0.10,
    "actionability": 0.10,
    "urgency": 0.10,
}

PENALTY_POINTS: dict[str, float] = {
    Penalty.DUPLICATE.value: -10.0,
    Penalty.PAYWALL.value: -10.0,
    Penalty.PRESS_RELEASE.value: -20.0,
    Penalty.SINGLE_SOURCE.value: -5.0,
}

# Transferability bands for foreign items (blueprint: 0.6-1.0).
TRANSFERABILITY_EU_REGULATORY = 0.95
TRANSFERABILITY_EU_GUIDELINE = 0.85
TRANSFERABILITY_SOLID_EVIDENCE = 0.75
TRANSFERABILITY_SYSTEM_DEPENDENT = 0.65

REGULATOR_SOURCE_MARKERS: tuple[str, ...] = ("ema", "ecdc", "who", "eu_")

GENERALISABLE_DOCUMENT_TYPES = frozenset({
    DocumentType.GUIDELINE,
    DocumentType.CONSENSUS,
    DocumentType.SAFETY_COMMUNICATION,
    DocumentType.SURVEILLANCE_REPORT,
})

SYSTEM_DEPENDENT_COUNTRIES = frozenset({"US", "UK"})
SOLID_EVIDENCE_MIN_TRUST = 3

# Deliberately below the dedup threshold (0.85): at or above that an item is
# dropped outright, and this band catches "same news rewritten".
DUPLICATE_TITLE_THRESHOLD = 0.75
SELF_SUFFICIENT_RELIABILITY = 3

_PAYWALL = re.compile(
    r"\b(paywall|subscribe\s+to\s+(read|continue)|abbonati\s+per|"
    r"contenuto\s+riservato\s+agli\s+abbonati|sign\s+in\s+to\s+read|"
    r"purchase\s+access|solo\s+per\s+abbonati)\b",
    re.IGNORECASE,
)
_PRESS_RELEASE = re.compile(
    r"\b(comunicato\s+stampa|press\s+release|nota\s+stampa)\b", re.IGNORECASE,
)
_DATA = re.compile(
    r"(\d+\s*%|\bp\s*[<=>]\s*0?\.\d+|\bIC\s*95|\b95%\s*CI|"
    r"\bn\s*=\s*\d+|\bsensibilit|\bspecificit|\bsensitivity\b|\bspecificity\b)",
    re.IGNORECASE,
)


def compute_raw_score(subscores: Subscores) -> float:
    """Compute raw score (0-100) from 7 subscores (0-5 each)."""
    weighted = (
        subscores.pls_relevance * WEIGHTS["pls_relevance"]
        + subscores.clinical_impact * WEIGHTS["clinical_impact"]
        + subscores.operational_impact * WEIGHTS["operational_impact"]
        + subscores.source_trust * WEIGHTS["source_trust"]
        + subscores.novelty * WEIGHTS["novelty"]
        + subscores.actionability * WEIGHTS["actionability"]
        + subscores.urgency * WEIGHTS["urgency"]
    )
    return weighted * (100.0 / 5.0)


def apply_penalties(raw_score: float, penalties: list[str]) -> float:
    """Apply noise penalties to raw score."""
    total = sum(PENALTY_POINTS.get(p, 0.0) for p in penalties)
    return max(0.0, min(100.0, raw_score + total))


def detect_penalties(item: NewsItem, recent_titles: list[str] | None = None) -> list[str]:
    """Return every noise penalty that applies to this item."""
    text = f"{item.content.title} {item.content.raw_text}"
    penalties: list[str] = []

    if recent_titles and _is_near_duplicate(item.content.title, recent_titles):
        penalties.append(Penalty.DUPLICATE.value)
    if _PAYWALL.search(text):
        penalties.append(Penalty.PAYWALL.value)
    if _PRESS_RELEASE.search(text) and not _DATA.search(text):
        penalties.append(Penalty.PRESS_RELEASE.value)
    if (
        item.source.reliability_tier < SELF_SUFFICIENT_RELIABILITY
        and len(item.editorial.citations) <= 1
    ):
        penalties.append(Penalty.SINGLE_SOURCE.value)

    return penalties


def _is_near_duplicate(title: str, recent_titles: list[str]) -> bool:
    normalised = title.lower().strip()
    if not normalised:
        return False
    return any(
        SequenceMatcher(None, normalised, other.lower().strip()).ratio()
        >= DUPLICATE_TITLE_THRESHOLD
        for other in recent_titles
    )


def compute_transferability(item: NewsItem) -> float:
    """Determine the Italy-transferability multiplier for a foreign item."""
    if item.classification.geo == Geo.IT:
        return 1.0

    if any(marker in item.source.key.lower() for marker in REGULATOR_SOURCE_MARKERS):
        return TRANSFERABILITY_EU_REGULATORY

    if item.classification.geo == Geo.EU:
        if item.content.document_type in GENERALISABLE_DOCUMENT_TYPES:
            return TRANSFERABILITY_EU_GUIDELINE
        return TRANSFERABILITY_SOLID_EVIDENCE

    if item.source.country in SYSTEM_DEPENDENT_COUNTRIES:
        if (
            item.content.document_type in GENERALISABLE_DOCUMENT_TYPES
            and item.scoring.subscores.source_trust >= SOLID_EVIDENCE_MIN_TRUST
        ):
            return TRANSFERABILITY_SOLID_EVIDENCE
        return TRANSFERABILITY_SYSTEM_DEPENDENT

    return TRANSFERABILITY_SOLID_EVIDENCE


def score_item(item: NewsItem) -> ScoringBlock:
    """Full scoring pipeline for a single item."""
    penalised = apply_penalties(
        compute_raw_score(item.scoring.subscores), item.scoring.penalties,
    )
    transferability = compute_transferability(item)

    return ScoringBlock(
        score_total=round(penalised * transferability, 2),
        subscores=item.scoring.subscores.model_copy(
            update={"transferability": transferability},
        ),
        penalties=item.scoring.penalties,
    )
