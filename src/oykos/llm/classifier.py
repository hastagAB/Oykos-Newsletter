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
of free choice (Pediatri di Libera Scelta) who run an outpatient practice.

Score each dimension 0-5 from the point of view of that reader:
- pls_relevance: impact on a typical outpatient or triage decision
- clinical_impact: reduces clinical risk or changes management
- operational_impact: changes workflow, timing, communication, paperwork
- source_trust: 5 institutional regulator, 4 national society, 3 peer-reviewed
  journal, 2 hospital/IRCCS, 1 secondary press, 0 unverified or marketing
- novelty: new versus what a well-read pediatrician already knew last month
- actionability: is there something to do, check, avoid or explain tomorrow
- urgency: seasonal, expiring, or immediately relevant

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

    resp = await client.triage_structured(
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
    )

    return classification, subscores
