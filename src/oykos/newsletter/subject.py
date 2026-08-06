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
Italian pediatricians of free choice (PLS).

Rules:
- Write in Italian, with correct accents.
- Maximum {SUBJECT_MAX_CHARS} characters for the subject.
- Name the topics and the consequence, leaving one useful question open.
  Interest must come from clinical relevance, never from withholding information.
  Good: "Asma, influenza, epilessia: cosa cambia davvero".
  Also good: "Attacco acuto d'asma: cosa non cambiare questa settimana".
- Never clickbait, no emoji, no ALL CAPS, no manufactured urgency.
- Never audit the reader: no "Hai visto...", no "Le tue pratiche sono allineate...".
- preheader: up to {PREHEADER_MAX_CHARS} characters anticipating the benefit of
  reading, complementing the subject rather than repeating it. For example
  "Tre aggiornamenti per il PLS, due verifiche utili e un documento da non
  modificare\"."""


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
