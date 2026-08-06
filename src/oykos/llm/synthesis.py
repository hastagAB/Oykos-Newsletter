"""Editorial synthesis - S019.

Produces the 5-block item template of the blueprint (Section 5) from the
evidence passages extracted in S018. The model never sees the raw document as
its only input: claims must be traceable to a numbered passage.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import Citation, EditorialBlock, NewsItem
from oykos.models.taxonomy import Confidence

logger = logging.getLogger(__name__)

HEADLINE_MAX_CHARS = 90
SOURCE_NOTE_MAX_CHARS = 140
MAX_ACTIONS = 1
MAX_FALLBACK_SUMMARY_CHARS = 500

SYNTHESIS_SYSTEM = f"""You are the clinical curator of an Italian pediatric
newsletter, writing for Pediatri di Libera Scelta. You have already read and
assessed the source; return only what is useful.

Voice: a very well prepared colleague. Competent, collegial, operational, sober.
Never put the reader under scrutiny. Never manufacture urgency or curiosity.

Every item answers: what changed, why it matters in practice, what to do now.

Rules:
- Write in Italian with correct accents: perche', piu', gia', cio', eta', e'
  must be written perch\u00e9, pi\u00f9, gi\u00e0, ci\u00f2, et\u00e0, \u00e8.
- headline_operational: a CONCLUDING title, max {HEADLINE_MAX_CHARS} characters, that
  already carries the consequence. Do not merely announce that a document exists.
  Good: "Attacco acuto d'asma: per ora non cambiare la pratica".
  Bad: "SICuPP pubblica un aggiornamento sull'asma".
- why_it_matters: one or two sentences on why this touches a PLS's practice.
  Open with the consequence, not the background, not with who published it.
  Write "In pratica, questo significa..." rather than "Per il PLS conta perche'...".
- what_to_do: EXACTLY ONE priority action, proportionate to how solid and how
  accessible the source is. Use concrete verbs - consultare, confrontare,
  ricontrollare, mantenere - always naming what must be checked.
  Never audit the reader. Write "Ricontrolla questi due aspetti della gestione",
  never "Verifica se le tue pratiche sono allineate".
- summary: 2 to 5 lines giving what the reader needs to decide whether to go
  deeper. Specifics over adjectives: ages, doses, dates, thresholds. No filler
  openers. Do not restate the headline or why_it_matters in other words.
- source_note: max {SOURCE_NOTE_MAX_CHARS} characters naming what kind of source this is and
  what it does NOT let you conclude, for example "Documento istituzionale. Testo
  integrale non accessibile." Never write a bare reliability grade.
- Ground every claim in the numbered EVIDENCE passages. Cite the passage number
  in supporting_passage_ref (for example "P2").
- Keep separate what the source states and what you infer. Never attribute a
  recommendation to a source whose full text you have not read.
- If ACCESS LIMITED is true this is a document notice, not a clinical
  recommendation. Say plainly that the full text is reserved to members, draw
  NO clinical conclusion from it, and make the single action about consulting
  the document if the reader has access, otherwise keeping current practice
  until a complete source is available. The headline must not imply a change
  in practice.
- Never write a therapeutic protocol unless the source is a national guideline
  or consensus document."""


class SynthesisCitation(BaseModel):
    claim_id: str
    source_url: str
    supporting_passage_ref: str = ""


class SynthesisResponse(BaseModel):
    headline_operational: str
    why_it_matters: str
    what_to_do: list[str] = Field(default_factory=list)
    summary: str
    source_note: str = ""
    confidence: str = "medium"
    citations: list[SynthesisCitation] = Field(default_factory=list)


def _format_evidence(item: NewsItem) -> str:
    if not item.content.key_passages:
        return "(no verbatim passages could be extracted from this source)"
    return "\n".join(
        f"P{i}: \"{passage.quote}\"" + (f" [{passage.location}]" if passage.location else "")
        for i, passage in enumerate(item.content.key_passages, start=1)
    )


async def synthesize_editorial(item: NewsItem, client: LLMClient) -> EditorialBlock:
    """Generate grounded editorial content for a scored news item."""
    prompt = f"""Write the newsletter item for this pediatric news article.

Title: {item.content.title}
Source: {item.source.name} ({item.source.country}, reliability {item.source.reliability_tier}/5)
URL: {item.content.canonical_url}
Document type: {item.content.document_type.value}
Classification: {', '.join(t.value for t in item.classification.taxonomy_tags) or 'n/a'}
Score: {item.scoring.score_total}/100
ACCESS LIMITED: {item.content.access_limited}

EVIDENCE (quote these, do not invent):
{_format_evidence(item)}"""

    try:
        resp = await client.complete_structured(
            prompt=prompt,
            response_model=SynthesisResponse,
            system=SYNTHESIS_SYSTEM,
        )
    except Exception:
        logger.exception("Synthesis failed for %s", item.content.title)
        return EditorialBlock(
            headline_operational=item.content.title[:HEADLINE_MAX_CHARS],
            summary=item.content.raw_text[:MAX_FALLBACK_SUMMARY_CHARS],
            confidence=Confidence.LOW,
        )

    valid_confidences = {c.value for c in Confidence}
    confidence = (
        Confidence(resp.confidence)
        if resp.confidence in valid_confidences
        else Confidence.MEDIUM
    )

    # No evidence means no defensible confidence, whatever the model claims.
    if not item.content.key_passages:
        confidence = Confidence.LOW

    citations = [
        Citation(
            claim_id=c.claim_id,
            source_url=c.source_url or item.content.canonical_url,
            supporting_passage_ref=c.supporting_passage_ref,
        )
        for c in resp.citations
        if c.claim_id
    ]

    return EditorialBlock(
        headline_operational=resp.headline_operational.strip()[:HEADLINE_MAX_CHARS],
        why_it_matters=resp.why_it_matters.strip(),
        what_to_do=[a.strip() for a in resp.what_to_do if a.strip()][:MAX_ACTIONS],
        summary=resp.summary.strip(),
        source_note=resp.source_note.strip()[:SOURCE_NOTE_MAX_CHARS],
        confidence=confidence,
        citations=citations,
    )
