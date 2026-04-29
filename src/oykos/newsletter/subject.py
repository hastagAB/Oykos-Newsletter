"""Subject line generator - S024."""
from __future__ import annotations

import logging

from oykos.llm.client import LLMClient
from oykos.models.news_item import Newsletter

logger = logging.getLogger(__name__)

SUBJECT_SYSTEM = """You are a newsletter subject line expert for Italian pediatric professionals.
Generate compelling, informative subject lines that highlight the most important item of the week.
Write in Italian. Keep under 60 characters. No clickbait."""


async def generate_subject_lines(
    newsletter: Newsletter,
    client: LLMClient,
) -> tuple[str, str]:
    """Generate primary and variant subject lines for A/B testing."""
    top_items = [
        slot.editorial.headline_operational
        for slot in newsletter.slots[:3]
        if slot.editorial.headline_operational
    ]

    if not top_items:
        default = f"L'Essenziale in Pediatria - {newsletter.week}"
        return default, default

    prompt = f"""Generate 2 subject lines for this week's pediatric newsletter ({newsletter.week}).

Top stories:
{chr(10).join(f'- {t}' for t in top_items)}

Rules:
- Max 60 characters each
- In Italian
- Professional, informative tone
- Line 1: Feature the top story
- Line 2: Alternative angle or summary approach

Return JSON: {{"subject_a": "...", "subject_b": "..."}}"""

    try:
        from pydantic import BaseModel

        class SubjectResponse(BaseModel):
            subject_a: str
            subject_b: str

        resp = await client.complete_structured(
            prompt=prompt,
            response_model=SubjectResponse,
            system=SUBJECT_SYSTEM,
        )
        return resp.subject_a[:80], resp.subject_b[:80]

    except Exception:
        logger.exception("Subject line generation failed")
        fallback = f"L'Essenziale in Pediatria - {newsletter.week}"
        return fallback, fallback
