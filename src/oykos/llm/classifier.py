"""LLM-based taxonomy classifier - S012.

Runs on the economy "triage" model (blueprint Section 1: a cheap model for
classification, the primary model for editorial synthesis). The response schema
is strict and enum-typed so no free-form label can enter the pipeline.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import Classification, NewsItem, Subscores
from oykos.models.taxonomy import DocumentType, Geo, Setting, TaxonomyTag

logger = logging.getLogger(__name__)

MAX_CLASSIFY_CHARS = 4000

CLASSIFY_SYSTEM = """You classify news for a newsletter read by Italian pediatricians
of free choice (Pediatri di Libera Scelta, PLS).

WHO THE READER IS. A PLS runs their own outpatient practice in the territory.
They follow a registered list of children from birth to adolescence over years.
Their day is well-child visits and growth monitoring, vaccination counselling,
common acute illness seen at the first presentation, chronic conditions followed
between specialist visits, family reassurance and health education, deciding
whether and when to refer, certificates, and practice organisation.

WHO THE READER IS NOT. They are not a hospital pediatrician. They do not run a
ward, an emergency department, an intensive care unit, or a neonatal unit. They
do not perform resuscitation procedures, inpatient management, or subspecialist
interventions. A story about what to do with a critically ill child in an
emergency department is clinically valid and still the wrong story for this
reader.

THE TEST THAT MATTERS. Before scoring, ask: what would this specific reader do
differently in their studio on Monday? If the honest answer is "nothing, this
belongs to a hospital team", pls_relevance must be 0-1 no matter how respected
the source is.

Score each dimension 0-5 from the point of view of that reader:
- pls_relevance: does it affect patients, decisions, counselling, follow up or
  workflow in an outpatient primary care practice? This is the first filter, not
  a tiebreaker. 5 = changes a recurring primary care decision. 3 = useful
  background for the studio. 0-1 = hospital, subspecialist or inpatient only.
- clinical_impact: reduces clinical risk or changes management in primary care
- operational_impact: changes workflow, timing, communication, paperwork
- source_trust: 5 institutional regulator, 4 national society or major
  peer-reviewed pediatric journal, 3 other peer-reviewed journal, 2
  hospital/IRCCS, 1 secondary press, 0 unverified or marketing.
  Judge the source on authority alone. An Italian source is NOT more
  trustworthy because it is Italian, and an international source is NOT less
  relevant because it is international.
- novelty: genuinely new versus what a well-read pediatrician knew last month.
  A generic educational reminder of settled practice is 0-1.
- actionability: can the reader understand what to consider or do differently
- urgency: seasonal, expiring, or immediately relevant

setting: use "territory" for outpatient primary care, "hospital" for inpatient,
emergency or subspecialist settings, "mixed" only when the content genuinely
serves both. Do not mark something "mixed" just because a PLS could read it.

italian_applicability: how well the content transfers to Italian PLS practice,
0.0-1.0. Foreign guidance that depends on another country's service
organisation transfers less well than evidence about a clinical decision.

Only assign taxonomy tags that clearly apply. Be conservative."""


class ClassificationResponse(BaseModel):
    """Strict schema - every field is required and enum constrained."""

    geo: Geo
    taxonomy_tags: list[TaxonomyTag] = Field(default_factory=list)
    setting: Setting
    document_type: DocumentType
    pls_relevance_ratio: float = Field(ge=0.0, le=1.0)
    device_related: bool
    tests_mentioned: list[str] = Field(default_factory=list)
    pls_relevance: int = Field(ge=0, le=5)
    clinical_impact: int = Field(ge=0, le=5)
    operational_impact: int = Field(ge=0, le=5)
    source_trust: int = Field(ge=0, le=5)
    novelty: int = Field(ge=0, le=5)
    actionability: int = Field(ge=0, le=5)
    urgency: int = Field(ge=0, le=5)
    italian_applicability: float = Field(default=1.0, ge=0.0, le=1.0)
    # One sentence naming what a PLS would do differently, or why nothing
    # changes for them. Kept for the review workbench and for debugging a bad
    # selection: a score with no stated reason cannot be argued with.
    pls_use_case: str = ""


async def classify_item(item: NewsItem, client: LLMClient) -> tuple[Classification, Subscores]:
    """Classify a news item and return its classification plus the 7 subscores.

    Also refines ``item.content.document_type`` in place, since the document type
    drives the gates, the alert triggers and the transferability band.

    Raises on API failure rather than returning zero subscores: a zeroed item is
    indistinguishable from one the model judged worthless, which would let an
    outage or an empty billing account look like a quiet news week.
    """
    prompt = f"""Classify this pediatric news article.

Title: {item.content.title}
Source: {item.source.name} ({item.source.country})
Declared reliability: {item.source.reliability_tier}/5
URL: {item.content.canonical_url}
Content:
{item.content.raw_text[:MAX_CLASSIFY_CHARS]}"""

    # The frontier model, not triage. Audience fit is the decision the whole
    # newsletter rests on, and the cheap model was picking hospital stories.
    resp = await client.complete_structured(
        prompt=prompt,
        response_model=ClassificationResponse,
        system=CLASSIFY_SYSTEM,
    )

    item.content.document_type = resp.document_type

    classification = Classification(
        geo=resp.geo,
        taxonomy_tags=list(dict.fromkeys(resp.taxonomy_tags)),
        setting=resp.setting,
        pls_relevance=resp.pls_relevance_ratio,
        device_related=resp.device_related,
        tests_mentioned=resp.tests_mentioned,
    )

    subscores = Subscores(
        pls_relevance=resp.pls_relevance,
        clinical_impact=resp.clinical_impact,
        operational_impact=resp.operational_impact,
        source_trust=resp.source_trust,
        novelty=resp.novelty,
        actionability=resp.actionability,
        urgency=resp.urgency,
        transferability=resp.italian_applicability,
    )

    if resp.pls_use_case:
        logger.debug("PLS use case for %s: %s", item.content.title[:60], resp.pls_use_case)

    return classification, subscores
