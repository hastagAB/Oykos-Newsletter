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
from oykos.models.taxonomy import ImplicationKind

logger = logging.getLogger(__name__)

SUBJECT_MAX_CHARS = 60
PREHEADER_MAX_CHARS = 120
CTA_TITLE_MAX_CHARS = 90
TOP_ITEMS_FOR_SUBJECT = 3

# Told to the subject writer so it cannot promise more than the issue delivers.
IMPLICATION_SUMMARY = {
    "changes_practice": "cambia la pratica",
    "worth_attention": "merita attenzione",
    "may_consider": "puo' essere utile considerare",
    "no_change": "non cambia la pratica",
    "insufficient": "evidenze non sufficienti",
}

SUBJECT_SYSTEM = f"""You write subject lines for a weekly briefing read by
Italian pediatricians of free choice (PLS).

The subject must not promise more than the issue delivers. Most weeks the
contents are things worth knowing, not changes in practice. A subject like
"cosa cambia ora" over an issue of observational studies is a false promise and
primes the reader to expect instructions.

You are told what each item actually concludes. Let that govern the subject:
- If nothing in the issue changes practice, do NOT use "cosa cambia", "cosa
  fare", "ora", "subito" or any other operational framing. Name the topics and
  the kind of knowledge they add.
- Only when an item genuinely changes practice may the subject say so.
- When only some items change practice, attribute the change to the source that
  issued it ("Nuove indicazioni AIFA su...") and never let it stand as the frame
  for the whole issue. "Cosa cambia questa settimana" over one regulatory notice
  and three observational studies misrepresents the other three. The subject and
  the preheader are both bound by this: neither may generalise one item's
  conclusion to the issue.

Rules:
- Write in Italian, with correct accents.
- Maximum {SUBJECT_MAX_CHARS} characters for the subject.
- Informative before catchy. Interest comes from clinical relevance, never from
  alarm or artificial curiosity.
  Good for an issue of observations:
  "Schermi e sonno, spirometria nei pretermine: i dati della settimana".
  Good when something really changes:
  "Nuove misure AIFA: cosa cambia nella prescrizione".
- Never clickbait, no emoji, no ALL CAPS, no manufactured urgency.
- Never audit the reader: no "Hai visto...", no "Le tue pratiche sono allineate...".
- preheader: up to {PREHEADER_MAX_CHARS} characters anticipating what the reader
  will find, complementing the subject rather than repeating it. Same rule: do
  not promise actions the issue does not contain.
- subject_variant_b: a second subject line taking a genuinely different angle on
  the same content. Same rules and same length limit. Not a paraphrase.
- preheader_variant_b: a second preheader, same rules and length limit, opening
  on a different aspect from the first. Not a paraphrase.
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
        f"{len(newsletter.slots)} aggiornamenti dalla settimana, "
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
        f"{slot.editorial.headline_operational} "
        f"[conclusione: {IMPLICATION_SUMMARY.get(slot.editorial.implication_kind.value, '')}]"
        for slot in newsletter.slots[:TOP_ITEMS_FOR_SUBJECT]
        if slot.editorial.headline_operational
    ]
    if not top_items:
        return _fallback(newsletter)

    changing = [
        slot.source_name or "la fonte"
        for slot in newsletter.slots
        if slot.editorial.implication_kind is ImplicationKind.CHANGES_PRACTICE
    ]
    if not changing:
        practice_note = (
            "Nothing in this issue changes practice, so operational framing is "
            "forbidden in both the subject and the preheader."
        )
    elif len(changing) < len(newsletter.slots):
        practice_note = (
            f"Only part of this issue changes practice: {', '.join(changing)}. "
            f"The other {len(newsletter.slots) - len(changing)} item(s) do not. "
            "If you mention the change, attribute it to that source by name. Do "
            "not frame the issue as a whole around it."
        )
    else:
        practice_note = "Every item in this issue changes practice."

    prompt = f"""Write the subject line for this week's briefing ({newsletter.week}).

Top stories, each with what it actually concludes:
{chr(10).join(f'- {t}' for t in top_items)}

{practice_note}

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
