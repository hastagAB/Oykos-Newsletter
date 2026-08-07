"""Subject line and preheader generator.

Benefit-driven, for example:

    "PLS Briefing: RSV/influenza + 1 alert AIFA + 2 cose da evitare in studio"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel

from oykos.llm.client import LLMClient
from oykos.models.news_item import Newsletter

logger = logging.getLogger(__name__)

SUBJECT_MAX_CHARS = 60
PREHEADER_MAX_CHARS = 120
CTA_TITLE_MAX_CHARS = 90
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
  modificare".
- subject_variant_b: a second subject line taking a genuinely different angle on
  the same content - for instance the clinical consequence where the first is
  operational. Same rules and same length limit. It must not be a paraphrase.
- preheader_variant_b: a second preheader, same rules and length limit, opening
  on a different benefit from the first. It must not be a paraphrase.
- cta_variant_b: an alternative wording for the closing call to action shown
  above the button, up to {CTA_TITLE_MAX_CHARS} characters. It promotes the
  Oykos product, so it must promise a working benefit and must never make a
  clinical claim or imply medical endorsement. It must not be a paraphrase of
  the current wording you are given."""


class SubjectResponse(BaseModel):
    subject: str
    preheader: str
    # Each is a genuinely different angle on the same content, for the A/B
    # comparison. Only the one matching AB_ELEMENT is ever used.
    subject_variant_b: str = ""
    preheader_variant_b: str = ""
    cta_variant_b: str = ""


@dataclass
class SubjectLines:
    """The A copy for an issue, plus one B candidate per testable element."""

    subject: str
    preheader: str
    subject_b: str = ""
    preheader_b: str = ""
    cta_b: str = ""

    def variant_for(self, element: str) -> str:
        """The B text for ``element``, or empty when there is nothing to test."""
        return {
            "subject": self.subject_b,
            "preheader": self.preheader_b,
            "cta": self.cta_b,
        }.get(element, "")


def _fallback(newsletter: Newsletter) -> SubjectLines:
    base = f"L'Essenziale in Pediatria - {newsletter.week}"
    preheader = (
        f"{len(newsletter.slots)} aggiornamenti operativi, "
        f"lettura {newsletter.reading_time_minutes} minuti."
    )
    return SubjectLines(
        subject=base[:SUBJECT_MAX_CHARS],
        preheader=preheader[:PREHEADER_MAX_CHARS],
    )


async def generate_subject_line(
    newsletter: Newsletter,
    client: LLMClient,
    current_cta_title: str = "",
) -> SubjectLines:
    """Generate the subject, preheader and one B candidate per testable element."""
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
{newsletter.reading_time_minutes} minutes to read.

The closing call to action currently reads:
{current_cta_title}"""

    try:
        # The frontier model, not triage: these few lines decide whether the
        # issue is opened at all, and the B variants must be real alternatives
        # rather than paraphrases for the comparison to mean anything.
        resp = await client.complete_structured(
            prompt=prompt,
            response_model=SubjectResponse,
            system=SUBJECT_SYSTEM,
        )
    except Exception:
        logger.exception("Subject line generation failed")
        return _fallback(newsletter)

    return SubjectLines(
        subject=resp.subject.strip()[:SUBJECT_MAX_CHARS],
        preheader=resp.preheader.strip()[:PREHEADER_MAX_CHARS],
        subject_b=resp.subject_variant_b.strip()[:SUBJECT_MAX_CHARS],
        preheader_b=resp.preheader_variant_b.strip()[:PREHEADER_MAX_CHARS],
        cta_b=resp.cta_variant_b.strip()[:CTA_TITLE_MAX_CHARS],
    )
