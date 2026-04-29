"""Claim verification - S020."""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import EditorialBlock
from oykos.models.taxonomy import Confidence

logger = logging.getLogger(__name__)

VERIFY_SYSTEM = """You are a fact-checking assistant for a pediatric medical newsletter.
Verify each claim in the editorial against the source material.
Flag any claims that are not directly supported by the cited sources.
Be conservative - lower confidence if evidence is indirect or incomplete."""


class VerificationResult(BaseModel):
    verified: bool = True
    issues: list[str] = Field(default_factory=list)
    adjusted_confidence: str = "medium"


async def verify_claims(
    editorial: EditorialBlock,
    source_text: str,
    client: LLMClient,
) -> EditorialBlock:
    """Verify editorial claims against source material, adjust confidence."""
    if not editorial.summary:
        return editorial

    prompt = f"""Verify the following editorial content against the source material:

EDITORIAL:
Headline: {editorial.headline_operational}
Summary: {editorial.summary}
Why it matters: {editorial.why_it_matters}
What to do:
{chr(10).join('- ' + a for a in editorial.what_to_do)}

SOURCE MATERIAL:
{source_text[:4000]}

Check:
1. Are all claims in the summary supported by the source?
2. Are the action items reasonable given the evidence?
3. Is the confidence level appropriate?

Respond with:
- verified: true/false
- issues: list of specific unsupported claims (empty if all verified)
- adjusted_confidence: high, medium, or low"""

    try:
        result = await client.complete_structured(
            prompt=prompt,
            response_model=VerificationResult,
            system=VERIFY_SYSTEM,
        )

        valid_confidences = {c.value for c in Confidence}
        new_confidence = (
            Confidence(result.adjusted_confidence)
            if result.adjusted_confidence in valid_confidences
            else editorial.confidence
        )

        if result.issues:
            editorial.review.needs_human_review = True

        editorial.confidence = new_confidence
        return editorial

    except Exception:
        logger.exception("Verification failed")
        editorial.review.needs_human_review = True
        return editorial
