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
HOOK_MAX_CHARS = 120
MIN_ACTIONS = 2
MAX_ACTIONS = 4
MAX_FALLBACK_SUMMARY_CHARS = 500

SYNTHESIS_SYSTEM = f"""You are a senior Italian pediatrician writing an operational
briefing for colleagues in primary care (Pediatri di Libera Scelta).

Every item must answer three questions in 20-40 seconds of reading:
what happened, why it matters for a PLS, what changes tomorrow morning in the studio.

Style rules:
- Write in Italian, with correct accents (attivita is wrong, attivita\u0300 is right:
  always write perche\u0301, piu\u0300, gia\u0300, cio\u0300, eta\u0300, e\u0300).
- hook_question: one question, maximum {HOOK_MAX_CHARS} characters, addressed to the
  reader as "tu", that makes a PLS check their own practice against this item.
  For example "Le prescrizioni e gli invii dei tuoi pazienti con epilessia sono in
  linea con le nuove raccomandazioni nazionali?" or "Di quali strumenti di
  diagnostica di primo livello e\u0300 dotato il tuo studio?". It must be answerable
  by the reader from their own practice, never rhetorical or generic. Ask about
  the reader's own patients, studio or prescribing, never about the document.
- headline_operational: action-oriented, maximum {HEADLINE_MAX_CHARS} characters.
- why_it_matters: exactly one sentence on the clinical or operational impact.
  Lead with the consequence for the reader's practice, not with who published it.
- what_to_do: {MIN_ACTIONS} to {MAX_ACTIONS} concrete micro-actions (check, avoid,
  adopt, explain to parents). Each one must name what to do to whom and when.
  "Valutare la letteratura" is useless; "Rivedere i criteri di invio in PS per la
  bronchiolite sotto i 3 mesi" is useful.
- summary: 3 to 6 lines of clinical/operational detail. Prefer specifics - ages,
  doses, dates, thresholds, numbers - over adjectives. No filler openers such as
  "Recentemente" or "E\u0300 importante sottolineare che".
- Ground every claim in the numbered EVIDENCE passages you are given. Cite the
  passage number in supporting_passage_ref (for example "P2").
- Never state a fact the passages do not support. If the evidence is thin, say so
  and set confidence to low.
- Do not write therapeutic protocols unless the source is a national guideline
  or consensus document."""


class SynthesisCitation(BaseModel):
    claim_id: str
    source_url: str
    supporting_passage_ref: str = ""


class SynthesisResponse(BaseModel):
    hook_question: str
    headline_operational: str
    why_it_matters: str
    what_to_do: list[str] = Field(default_factory=list)
    summary: str
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
        hook_question=resp.hook_question.strip()[:HOOK_MAX_CHARS],
        headline_operational=resp.headline_operational.strip()[:HEADLINE_MAX_CHARS],
        why_it_matters=resp.why_it_matters.strip(),
        what_to_do=[a.strip() for a in resp.what_to_do if a.strip()][:MAX_ACTIONS],
        summary=resp.summary.strip(),
        confidence=confidence,
        citations=citations,
    )
