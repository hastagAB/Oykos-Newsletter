"""Three selection gates and exclusion criteria - blueprint Section 3.

An item enters the candidate set only if it passes ALL three gates:

* Gate 1 - PLS relevance: it must impact a territorial clinical decision, the
  organisation of the practice, an obligation, an implementable test/device, or
  useful training.
* Gate 2 - Reliability: institutional source, scientific society or reliable
  journal. A secondary source qualifies only when it links a primary source.
* Gate 3 - Actionability: there must be at least one recommended action, or a
  rule/novelty that reduces risk.

Exclusion criteria drop an item regardless of score:

* generalist medical news without change-in-practice
* preprints, which are never a main item
* vendor marketing press releases
* anything from a source too weak to stand behind
"""
from __future__ import annotations

import re

from oykos.models.news_item import Gating, NewsItem
from oykos.models.taxonomy import DocumentType, ExclusionReason, TaxonomyTag

# Gate 1 - a taxonomy tag alone proves relevance to the PLS working day.
PLS_RELEVANT_TAGS: frozenset[TaxonomyTag] = frozenset(TaxonomyTag)

# Gate 2 - minimum source reliability. 0-1 are secondary press/marketing.
MIN_RELIABILITY_TIER = 2

# Gate 2 - a secondary source is admissible only when it cites a primary one.
PRIMARY_SOURCE_DOMAINS: tuple[str, ...] = (
    "salute.gov.it",
    "iss.it",
    "epicentro.iss.it",
    "aifa.gov.it",
    "sisac.info",
    "garanteprivacy.it",
    "agenas.gov.it",
    "ema.europa.eu",
    "ecdc.europa.eu",
    "who.int",
    "gazzettaufficiale.it",
)

# Gate 3 - document types that are actionable by construction.
ACTIONABLE_DOCUMENT_TYPES: frozenset[DocumentType] = frozenset({
    DocumentType.SAFETY_COMMUNICATION,
    DocumentType.GUIDELINE,
    DocumentType.CONSENSUS,
    DocumentType.LEGAL_UPDATE,
    DocumentType.SURVEILLANCE_REPORT,
    DocumentType.EVENT,
})

MIN_ACTIONABILITY_SUBSCORE = 2
MIN_PLS_RELEVANCE_SUBSCORE = 2
# Source trust at or below this cannot carry a published item.
LOW_TRUST_SUBSCORE = 2

_PREPRINT_PATTERN = re.compile(
    r"\b(preprint|medrxiv|biorxiv|non\s+sottoposto\s+a\s+revisione|"
    r"not\s+peer[-\s]reviewed)\b",
    re.IGNORECASE,
)

_MARKETING_PATTERN = re.compile(
    r"\b(comunicato\s+stampa|press\s+release|lancia\s+sul\s+mercato|"
    r"nuova\s+gamma|leader\s+di\s+mercato|partnership\s+strategica|"
    r"announces\s+the\s+launch|now\s+available\s+for\s+purchase)\b",
    re.IGNORECASE,
)


def _cites_primary_source(item: NewsItem) -> bool:
    """True when a secondary item links back to an institutional primary source."""
    haystack = f"{item.content.raw_text} {item.content.canonical_url}".lower()
    if any(domain in haystack for domain in PRIMARY_SOURCE_DOMAINS):
        return True
    return any(
        any(domain in citation.source_url.lower() for domain in PRIMARY_SOURCE_DOMAINS)
        for citation in item.editorial.citations
    )


def passes_pls_relevance(item: NewsItem) -> bool:
    """Gate 1: does this change something for a pediatrician of free choice?"""
    if not item.classification.taxonomy_tags:
        return False
    if not PLS_RELEVANT_TAGS.intersection(item.classification.taxonomy_tags):
        return False
    return item.scoring.subscores.pls_relevance >= MIN_PLS_RELEVANCE_SUBSCORE


def passes_reliability(item: NewsItem) -> bool:
    """Gate 2: institutional/society/journal source, or secondary citing primary.

    A low ``source_trust`` subscore vetoes the gate outright: the registry tier says
    what a source usually is, the subscore says what this particular item actually is,
    and the harsher of the two wins.
    """
    if item.scoring.subscores.source_trust <= LOW_TRUST_SUBSCORE:
        return False
    if item.source.reliability_tier >= MIN_RELIABILITY_TIER:
        return True
    return _cites_primary_source(item)


def passes_actionability(item: NewsItem) -> bool:
    """Gate 3: at least one action to take, or a risk-reducing rule."""
    if item.editorial.what_to_do:
        return True
    if item.content.document_type in ACTIONABLE_DOCUMENT_TYPES:
        return True
    return item.scoring.subscores.actionability >= MIN_ACTIONABILITY_SUBSCORE


def is_preprint(item: NewsItem) -> bool:
    """Preprints may only appear in Radar, never as a main item."""
    return bool(_PREPRINT_PATTERN.search(f"{item.content.title} {item.content.raw_text}"))


def is_vendor_marketing(item: NewsItem) -> bool:
    """Company marketing is a signal to verify, never a primary source."""
    if item.source.reliability_tier > 1:
        return False
    return bool(_MARKETING_PATTERN.search(f"{item.content.title} {item.content.raw_text}"))


def is_generalist_news(item: NewsItem) -> bool:
    """Generalist medical news with no change-in-practice."""
    if item.content.document_type is not DocumentType.NEWS:
        return False
    subscores = item.scoring.subscores
    return (
        subscores.actionability < MIN_ACTIONABILITY_SUBSCORE
        and subscores.operational_impact < MIN_ACTIONABILITY_SUBSCORE
        and subscores.clinical_impact < MIN_ACTIONABILITY_SUBSCORE
    )


def evaluate_gates(item: NewsItem) -> Gating:
    """Run the three gates plus the exclusion criteria for a single item."""
    exclusions: list[ExclusionReason] = []

    if not passes_pls_relevance(item):
        exclusions.append(ExclusionReason.NO_PLS_RELEVANCE)
    if not passes_reliability(item):
        exclusions.append(ExclusionReason.UNRELIABLE_SOURCE)
    if not passes_actionability(item):
        exclusions.append(ExclusionReason.NOT_ACTIONABLE)
    if is_generalist_news(item):
        exclusions.append(ExclusionReason.GENERALIST_NEWS)
    if is_vendor_marketing(item):
        exclusions.append(ExclusionReason.VENDOR_MARKETING)
    if is_preprint(item):
        exclusions.append(ExclusionReason.PREPRINT)

    return Gating(passed=not exclusions, exclusions=exclusions)


def filter_candidates(items: list[NewsItem]) -> list[NewsItem]:
    """Apply the gates to a batch, annotating each item and keeping the survivors."""
    survivors: list[NewsItem] = []
    for item in items:
        item.gating = evaluate_gates(item)
        if item.gating.passed:
            survivors.append(item)
    return survivors
