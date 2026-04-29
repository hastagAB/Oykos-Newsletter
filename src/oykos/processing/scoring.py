"""7-dimension scoring engine - S013."""
from __future__ import annotations

from oykos.models.news_item import NewsItem, ScoringBlock, Subscores
from oykos.models.taxonomy import Geo

# Weights per scoring.md
WEIGHTS = {
    "pls_relevance": 0.22,
    "clinical_impact": 0.18,
    "operational_impact": 0.15,
    "source_trust": 0.15,
    "novelty": 0.10,
    "actionability": 0.10,
    "urgency": 0.10,
}

# Noise penalties
PENALTY_DUPLICATE = -10.0
PENALTY_PAYWALL = -10.0
PENALTY_PRESS_RELEASE = -20.0
PENALTY_SINGLE_SOURCE = -5.0

# Transferability ranges by category
TRANSFERABILITY_RANGES = {
    "eu_regulatory": (0.9, 1.0),
    "eu_guideline": (0.8, 0.9),
    "solid_evidence": (0.7, 0.8),
    "system_dependent": (0.6, 0.7),
}


def compute_raw_score(subscores: Subscores) -> float:
    """Compute raw score (0-100) from 7 subscores (0-5 each)."""
    weighted_sum = (
        subscores.pls_relevance * WEIGHTS["pls_relevance"]
        + subscores.clinical_impact * WEIGHTS["clinical_impact"]
        + subscores.operational_impact * WEIGHTS["operational_impact"]
        + subscores.source_trust * WEIGHTS["source_trust"]
        + subscores.novelty * WEIGHTS["novelty"]
        + subscores.actionability * WEIGHTS["actionability"]
        + subscores.urgency * WEIGHTS["urgency"]
    )
    return weighted_sum * (100.0 / 5.0)


def apply_penalties(raw_score: float, penalties: list[str]) -> float:
    """Apply noise penalties to raw score."""
    penalty_map = {
        "duplicate": PENALTY_DUPLICATE,
        "paywall": PENALTY_PAYWALL,
        "press_release": PENALTY_PRESS_RELEASE,
        "single_source": PENALTY_SINGLE_SOURCE,
    }
    total_penalty = sum(penalty_map.get(p, 0.0) for p in penalties)
    return max(0.0, min(100.0, raw_score + total_penalty))


def compute_transferability(item: NewsItem) -> float:
    """Determine transferability multiplier for non-Italian items."""
    if item.classification.geo == Geo.IT:
        return 1.0

    # EU regulatory bodies get highest transferability
    source_key = item.source.key.lower()
    if any(k in source_key for k in ("ema", "ecdc", "eu_")):
        return 0.95

    if item.classification.geo == Geo.EU:
        return 0.85

    # Global: depends on evidence quality
    return 0.70


def score_item(item: NewsItem) -> ScoringBlock:
    """Full scoring pipeline for a single item."""
    raw = compute_raw_score(item.scoring.subscores)
    penalized = apply_penalties(raw, item.scoring.penalties)
    transferability = compute_transferability(item)
    final_score = penalized * transferability

    return ScoringBlock(
        score_total=round(final_score, 2),
        subscores=item.scoring.subscores,
        penalties=item.scoring.penalties,
        transferability=transferability,
    )
