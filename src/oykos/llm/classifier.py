"""LLM-based taxonomy classifier - S012."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import Classification, NewsItem, Subscores
from oykos.models.taxonomy import DocumentType, Geo, Setting, TaxonomyTag

logger = logging.getLogger(__name__)

CLASSIFY_SYSTEM = """You are an expert Italian pediatrics news classifier.
Analyze the article and provide structured classification data.
Focus on relevance to Italian pediatric primary care (Pediatri di Libera Scelta).
Be precise with taxonomy tags - only assign tags that clearly apply."""


class ClassificationResponse(BaseModel):
    geo: str = "IT"
    taxonomy_tags: list[str] = Field(default_factory=list)
    setting: str = "territory"
    pls_relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    device_related: bool = False
    document_type: str = "news"
    subscores: dict[str, int] = Field(default_factory=dict)


async def classify_item(item: NewsItem, client: LLMClient) -> tuple[Classification, Subscores]:
    """Classify a news item using LLM and return updated classification + subscores."""
    prompt = f"""Classify this pediatric news article:

Title: {item.content.title}
Source: {item.source.name} ({item.source.country})
Content: {item.content.raw_text[:2000]}

Provide:
1. geo: IT, EU, or GLOBAL
2. taxonomy_tags: list from [{', '.join(t.value for t in TaxonomyTag)}]
3. setting: territory, hospital, or mixed
4. pls_relevance: 0.0-1.0 (relevance to PLS pediatricians)
5. device_related: true/false
6. document_type: one of [{', '.join(d.value for d in DocumentType)}]
7. subscores: dict with keys [pls_relevance, clinical_impact, operational_impact, source_trust, novelty, actionability, urgency], each 0-5"""

    try:
        resp = await client.complete_structured(
            prompt=prompt,
            response_model=ClassificationResponse,
            system=CLASSIFY_SYSTEM,
        )

        # Parse and validate
        valid_tags = {t.value for t in TaxonomyTag}
        tags = [TaxonomyTag(t) for t in resp.taxonomy_tags if t in valid_tags]

        classification = Classification(
            geo=Geo(resp.geo) if resp.geo in {g.value for g in Geo} else Geo.IT,
            taxonomy_tags=tags,
            setting=Setting(resp.setting) if resp.setting in {s.value for s in Setting} else Setting.TERRITORY,
            pls_relevance=resp.pls_relevance,
            device_related=resp.device_related,
        )

        sub = resp.subscores
        subscores = Subscores(
            pls_relevance=_clamp(sub.get("pls_relevance", 0)),
            clinical_impact=_clamp(sub.get("clinical_impact", 0)),
            operational_impact=_clamp(sub.get("operational_impact", 0)),
            source_trust=_clamp(sub.get("source_trust", 0)),
            novelty=_clamp(sub.get("novelty", 0)),
            actionability=_clamp(sub.get("actionability", 0)),
            urgency=_clamp(sub.get("urgency", 0)),
        )

        return classification, subscores

    except Exception:
        logger.exception("Classification failed for %s", item.content.title)
        return item.classification, Subscores()


def _clamp(value: int, lo: int = 0, hi: int = 5) -> int:
    return max(lo, min(hi, int(value)))
