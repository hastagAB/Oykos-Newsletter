"""Scoring and noise penalties - docs/scoring.md.

Audience fit is evaluated before source geography. The newsletter is read by
Pediatri di Libera Scelta, who work in an outpatient practice in the territory:
a clinically sound story aimed at a hospital team is the wrong story, however
authoritative the source. Weights follow the editorial feedback of 2026-08-07.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from oykos.models.news_item import NewsItem, ScoringBlock, Subscores
from oykos.models.taxonomy import DocumentType, Geo, Penalty, Setting

# The five criteria from the editorial feedback. Relevance to daily PLS practice
# and actionability together carry 60%, so authority alone can no longer carry a
# story that a PLS cannot use.
WEIGHTS = {
    "pls_relevance": 0.35,
    "actionability": 0.25,
    "source_trust": 0.15,
    "novelty": 0.15,
    "italian_applicability": 0.10,
}

# pls_relevance is the headline criterion, but "affects patients, decisions,
# counselling, follow up or workflow in primary care" is what the three
# practice-facing subscores measure together.
PRACTICE_BLEND = {
    "pls_relevance": 0.60,
    "operational_impact": 0.20,
    "clinical_impact": 0.20,
}

PENALTY_POINTS: dict[str, float] = {
    Penalty.DUPLICATE.value: -10.0,
    Penalty.PAYWALL.value: -10.0,
    Penalty.PRESS_RELEASE.value: -20.0,
    Penalty.SINGLE_SOURCE.value: -5.0,
    # "A story that is mainly hospital only should lose significant points
    # unless there is a clear and realistic PLS use case."
    Penalty.HOSPITAL_ONLY.value: -25.0,
    Penalty.CASE_REPORT.value: -15.0,
    Penalty.GENERIC_REMINDER.value: -12.0,
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

# A hospital-setting item escapes the penalty only with a clear PLS use case.
PLS_USE_CASE_MIN_RELEVANCE = 4
ACTIONABLE_MIN = 3
NOVELTY_MIN = 3
REMINDER_DOCUMENT_TYPES = frozenset({DocumentType.NEWS, DocumentType.EVENT})

_CASE_REPORT = re.compile(
    r"\b(case\s+report|a\s+case\s+of|caso\s+clinico|descriviamo\s+il\s+caso|"
    r"we\s+(report|describe)\s+(a|the)\s+case)\b",
    re.IGNORECASE,
)

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
    """Compute raw score (0-100) from the five weighted criteria."""
    practice = (
        subscores.pls_relevance * PRACTICE_BLEND["pls_relevance"]
        + subscores.operational_impact * PRACTICE_BLEND["operational_impact"]
        + subscores.clinical_impact * PRACTICE_BLEND["clinical_impact"]
    )
    weighted = (
        practice * WEIGHTS["pls_relevance"]
        + subscores.actionability * WEIGHTS["actionability"]
        + subscores.source_trust * WEIGHTS["source_trust"]
        + subscores.novelty * WEIGHTS["novelty"]
        # Italian applicability is already a 0-1 ratio, so it is scaled onto the
        # same 0-5 range as the other criteria before weighting.
        + subscores.transferability * 5.0 * WEIGHTS["italian_applicability"]
    )
    return weighted * (100.0 / 5.0)


def apply_penalties(raw_score: float, penalties: list[str]) -> float:
    """Apply noise penalties to raw score."""
    total = sum(PENALTY_POINTS.get(p, 0.0) for p in penalties)
    return max(0.0, min(100.0, raw_score + total))


def detect_penalties(item: NewsItem, recent_titles: list[str] | None = None) -> list[str]:
    """Penalties detectable from the raw item, at ingestion time."""
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


def detect_editorial_penalties(item: NewsItem) -> list[str]:
    """Penalties that can only be judged once the item has been classified.

    These depend on the setting and the subscores, which do not exist at
    ingestion time, so they must be applied after classification or they never
    fire at all.
    """
    penalties: list[str] = []
    if _is_hospital_only(item):
        penalties.append(Penalty.HOSPITAL_ONLY.value)
    if _is_case_report_without_implication(item):
        penalties.append(Penalty.CASE_REPORT.value)
    if _is_generic_reminder(item):
        penalties.append(Penalty.GENERIC_REMINDER.value)
    return penalties


def _is_hospital_only(item: NewsItem) -> bool:
    """Hospital-setting content with no realistic outpatient use case.

    The classifier judges the setting; a high operational or clinical score for
    primary care is what rescues an item, so a hospital story that genuinely
    changes something in the studio is not penalised.
    """
    if item.classification.setting != Setting.HOSPITAL:
        return False
    return item.scoring.subscores.pls_relevance < PLS_USE_CASE_MIN_RELEVANCE


def _is_case_report_without_implication(item: NewsItem) -> bool:
    """A single case with nothing to change is a story, not an update."""
    if not _CASE_REPORT.search(f"{item.content.title} {item.content.raw_text[:2000]}"):
        return False
    return item.scoring.subscores.actionability < ACTIONABLE_MIN


def _is_generic_reminder(item: NewsItem) -> bool:
    """Educational recap of settled practice: ranks below new evidence."""
    if item.scoring.subscores.novelty >= NOVELTY_MIN:
        return False
    return item.content.document_type in REMINDER_DOCUMENT_TYPES


def _is_near_duplicate(title: str, recent_titles: list[str]) -> bool:
    normalised = title.lower().strip()
    if not normalised:
        return False
    return any(
        SequenceMatcher(None, normalised, other.lower().strip()).ratio()
        >= DUPLICATE_TITLE_THRESHOLD
        for other in recent_titles
    )


def default_applicability(item: NewsItem) -> float:
    """Deterministic fallback for Italian applicability.

    Used only when the classifier did not judge it, for instance on items scored
    before the criterion existed. The judged value is preferred: a keyword band
    cannot tell evidence about a clinical decision apart from guidance that
    depends on another country's service organisation.
    """
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
    """Full scoring pipeline for a single item.

    Italian applicability is one weighted criterion worth 10%, judged by the
    classifier. It is deliberately NOT also a multiplier on the total: applying
    it twice is what let source geography outrank audience fit.
    """
    penalised = apply_penalties(
        compute_raw_score(item.scoring.subscores), item.scoring.penalties,
    )

    return ScoringBlock(
        score_total=round(penalised, 2),
        subscores=item.scoring.subscores,
        penalties=item.scoring.penalties,
    )
