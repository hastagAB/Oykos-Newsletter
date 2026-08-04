"""Claim verification - S020.

Blueprint Section 7: "if a claim is not supported by the snippets, downgrade the
confidence or block". This module is the gate that turns editorial text into
publishable text - it can and does refuse items.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import EditorialBlock, NewsItem
from oykos.models.taxonomy import Confidence

logger = logging.getLogger(__name__)

# More unsupported claims than this and the item is not publishable at all.
BLOCKING_UNSUPPORTED_CLAIMS = 2

# Sources that can corroborate each other (blueprint: AIFA <-> EMA, ISS <-> Ministry).
CROSS_SOURCE_PAIRS: dict[str, frozenset[str]] = {
    "aifa_safety": frozenset({"ema_news"}),
    "ema_news": frozenset({"aifa_safety"}),
    "iss_epicentro": frozenset({"respivirnet", "min_salute_pnpv"}),
    "respivirnet": frozenset({"iss_epicentro", "min_salute_pnpv"}),
    "min_salute_fsn": frozenset({"min_salute_dm_db"}),
}

VERIFY_SYSTEM = """You are a fact-checking assistant for a pediatric medical newsletter.

You are given editorial text and the verbatim EVIDENCE passages it was written from.
Check the FACTUAL ASSERTIONS in the editorial against those passages only.

What counts as a factual assertion: what a source published, what a guideline or
authority states, numbers, dates, dosages, thresholds, lot numbers, product names,
epidemiological figures, and any claim about what changed.

What does NOT count: the newsletter's own operational advice to the reader. This
publication exists to translate evidence into practice, so guidance such as
"check your stock", "update the reminder to parents" or "review your criteria"
is editorial by design and is labelled as such to readers. Flag that guidance
ONLY when it contradicts the evidence, or when it smuggles in a clinical
specific (a dose, an age cut-off, a threshold) that the passages do not state.

Rules:
- A factual assertion is supported only if a passage states it, not if a passage
  merely hints at it.
- List each unsupported assertion verbatim in `unsupported_claims`.
- Be conservative on facts: indirect or incomplete evidence means lower confidence."""


class VerificationResult(BaseModel):
    verified: bool = True
    unsupported_claims: list[str] = Field(default_factory=list)
    adjusted_confidence: str = "medium"


def _format_evidence(item: NewsItem) -> str:
    return "\n".join(
        f"P{i}: \"{passage.quote}\""
        for i, passage in enumerate(item.content.key_passages, start=1)
    )


def cross_source_support(item: NewsItem, corroborating_source_keys: set[str]) -> bool:
    """True when a paired institutional source also covers this topic."""
    partners = CROSS_SOURCE_PAIRS.get(item.source.key, frozenset())
    return bool(partners & corroborating_source_keys)


async def verify_claims(
    editorial: EditorialBlock,
    item: NewsItem,
    client: LLMClient,
) -> EditorialBlock:
    """Verify editorial claims against the extracted passages.

    Downgrades confidence, records unsupported claims and blocks the item when
    too many claims are ungrounded.
    """
    if not editorial.summary:
        return editorial

    # No evidence at all: nothing can be verified, so nothing can be trusted.
    if not item.content.key_passages:
        editorial.confidence = Confidence.LOW
        editorial.review.needs_human_review = True
        editorial.blocked = True
        logger.warning("Blocking ungrounded item: %s", item.content.title)
        return editorial

    prompt = f"""Verify this editorial against the evidence passages.

FACTUAL ASSERTIONS TO CHECK:
Headline: {editorial.headline_operational}
Why it matters: {editorial.why_it_matters}
Summary: {editorial.summary}

EDITORIAL GUIDANCE (check only for contradictions or invented clinical specifics):
{chr(10).join('- ' + a for a in editorial.what_to_do)}

EVIDENCE PASSAGES:
{_format_evidence(item)}"""

    try:
        result = await client.complete_structured(
            prompt=prompt,
            response_model=VerificationResult,
            system=VERIFY_SYSTEM,
        )
    except Exception:
        logger.exception("Verification failed for %s", item.content.title)
        editorial.confidence = Confidence.LOW
        editorial.review.needs_human_review = True
        return editorial

    valid_confidences = {c.value for c in Confidence}
    if result.adjusted_confidence in valid_confidences:
        editorial.confidence = Confidence(result.adjusted_confidence)

    unsupported = [c.strip() for c in result.unsupported_claims if c.strip()]
    editorial.unsupported_claims = unsupported

    if unsupported:
        editorial.review.needs_human_review = True
        editorial.confidence = Confidence.LOW
        if len(unsupported) >= BLOCKING_UNSUPPORTED_CLAIMS:
            editorial.blocked = True
            logger.warning(
                "Blocking item with %d unsupported claims: %s",
                len(unsupported),
                item.content.title,
            )

    return editorial
