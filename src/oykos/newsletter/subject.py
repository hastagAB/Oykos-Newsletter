"""Subject line and preheader generator.

Benefit-driven, for example:

    "PLS Briefing: RSV/influenza + 1 alert AIFA + 2 cose da evitare in studio"
"""
from __future__ import annotations

import logging

from pydantic import BaseModel

from oykos.llm.client import LLMClient
from oykos.models.news_item import Newsletter

logger = logging.getLogger(__name__)

SUBJECT_MAX_CHARS = 60
PREHEADER_MAX_CHARS = 120
TOP_ITEMS_FOR_SUBJECT = 3

SUBJECT_SYSTEM = f"""You write subject lines for a weekly operational briefing read by
Italian pediatricians of free choice.

Rules:
- Write in Italian.
- Maximum {SUBJECT_MAX_CHARS} characters for the subject.
- Benefit-driven and concrete: name what the reader gains or must not miss.
- Professional, never clickbait, no emoji, no ALL CAPS.
- preheader: up to {PREHEADER_MAX_CHARS} characters that complement the subject
  rather than repeating it."""


class SubjectResponse(BaseModel):
    subject: str
    preheader: str


def _fallback(newsletter: Newsletter) -> tuple[str, str]:
    base = f"L'Essenziale in Pediatria - {newsletter.week}"
    preheader = (
        f"{len(newsletter.slots)} aggiornamenti operativi, "
        f"lettura {newsletter.reading_time_minutes} minuti."
    )
    return base[:SUBJECT_MAX_CHARS], preheader[:PREHEADER_MAX_CHARS]


async def generate_subject_line(
    newsletter: Newsletter,
    client: LLMClient,
) -> tuple[str, str]:
    """Generate (subject, preheader) for the issue."""
    top_items = [
        slot.editorial.headline_operational
        for slot in newsletter.slots[:TOP_ITEMS_FOR_SUBJECT]
        if slot.editorial.headline_operational
    ]
    if not top_items:
        return _fallback(newsletter)

    prompt = f"""Write the subject line for this week's briefing ({newsletter.week}).

Top stories:
{chr(10).join(f'- {t}' for t in top_items)}

The issue has {len(newsletter.slots)} items and takes about
{newsletter.reading_time_minutes} minutes to read."""

    try:
        resp = await client.triage_structured(
            prompt=prompt,
            response_model=SubjectResponse,
            system=SUBJECT_SYSTEM,
        )
    except Exception:
        logger.exception("Subject line generation failed")
        return _fallback(newsletter)

    return (
        resp.subject.strip()[:SUBJECT_MAX_CHARS],
        resp.preheader.strip()[:PREHEADER_MAX_CHARS],
    )
