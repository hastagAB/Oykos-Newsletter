"""Editorial synthesis - S019."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import Citation, EditorialBlock, NewsItem
from oykos.models.taxonomy import Confidence

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM = """You are a senior Italian pediatrician writing concise, actionable summaries for primary care colleagues (Pediatri di Libera Scelta).

Style rules:
- Write in Italian
- Use clear, direct language
- Focus on "what to do tomorrow" for a busy PLS
- Headline must be operational (verb-led or action-oriented)
- Why it matters: 1-2 sentences on clinical/operational impact
- What to do: 2-4 bullet points with concrete actions
- Summary: 3-5 sentences covering key evidence and context"""


class SynthesisResponse(BaseModel):
    headline_operational: str
    why_it_matters: str
    what_to_do: list[str] = Field(default_factory=list)
    summary: str
    confidence: str = "medium"
    citations: list[dict[str, str]] = Field(default_factory=list)


async def synthesize_editorial(item: NewsItem, client: LLMClient) -> EditorialBlock:
    """Generate editorial content for a scored news item."""
    prompt = f"""Write editorial content for this pediatric news article:

Title: {item.content.title}
Source: {item.source.name} ({item.source.country}, reliability: {item.source.reliability_tier}/5)
Content: {item.content.raw_text[:3000]}
Classification: {', '.join(t.value for t in item.classification.taxonomy_tags)}
Score: {item.scoring.score_total}/100

Generate:
1. headline_operational: Italian, action-oriented headline (max 120 chars)
2. why_it_matters: 1-2 sentences in Italian explaining clinical/operational impact
3. what_to_do: 2-4 bullet points with concrete actions for PLS
4. summary: 3-5 sentences covering key evidence and context
5. confidence: high, medium, or low
6. citations: list of {{claim_id, source_url, supporting_passage_ref}}"""

    try:
        resp = await client.complete_structured(
            prompt=prompt,
            response_model=SynthesisResponse,
            system=SYNTHESIS_SYSTEM,
        )

        valid_confidences = {c.value for c in Confidence}
        confidence = Confidence(resp.confidence) if resp.confidence in valid_confidences else Confidence.MEDIUM

        citations = []
        for c in resp.citations:
            if "claim_id" in c and "source_url" in c:
                citations.append(Citation(
                    claim_id=c["claim_id"],
                    source_url=c["source_url"],
                    supporting_passage_ref=c.get("supporting_passage_ref", ""),
                ))

        return EditorialBlock(
            headline_operational=resp.headline_operational,
            why_it_matters=resp.why_it_matters,
            what_to_do=resp.what_to_do,
            summary=resp.summary,
            confidence=confidence,
            citations=citations,
        )

    except Exception:
        logger.exception("Synthesis failed for %s", item.content.title)
        return EditorialBlock(
            headline_operational=item.content.title,
            summary=item.content.raw_text[:500],
            confidence=Confidence.LOW,
        )
