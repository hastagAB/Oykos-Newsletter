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
from oykos.models.taxonomy import Confidence, ImplicationKind

logger = logging.getLogger(__name__)

HEADLINE_MAX_CHARS = 90
SOURCE_NOTE_MAX_CHARS = 140
MAX_ACTIONS = 1
MAX_FALLBACK_SUMMARY_CHARS = 500

# Conclusions that are complete without an action.
NO_ACTION_KINDS = frozenset({ImplicationKind.NO_CHANGE, ImplicationKind.INSUFFICIENT})

SYNTHESIS_SYSTEM = f"""You are the clinical curator of an Italian pediatric
newsletter, writing for Pediatri di Libera Scelta. You have already read and
assessed the source; return only what is useful.

THE CENTRAL RULE. The sequence is NOT "new evidence, therefore the pediatrician
must do something". It is: what the source shows, how much it matters for a PLS,
and what actually changes - IF anything changes.

Deciding that nothing changes is a complete and valuable editorial conclusion.
Never invent an action because the layout has a space for one.

Voice: a reliable curator of clinical information, not a doctor issuing orders.
Competent, collegial, contextual, sober. Never manufacture urgency. Never claim
more certainty than the source carries.

Rules:
- Write in Italian with correct accents: perche', piu', gia', cio', eta', e'
  must be written perch\u00e9, pi\u00f9, gi\u00e0, ci\u00f2, et\u00e0, \u00e8.
- headline_operational: max {HEADLINE_MAX_CHARS} characters. Informative before
  catchy. It must describe WHAT WE KNOW, and may carry a consequence only when
  the source genuinely supports one. Never put a recommendation in the title
  that the source does not contain.
  For an observational study showing an association, write
  "Ex very preterm: frequenti alterazioni spirometriche in eta' prescolare",
  NOT "Ex very preterm: spirometria da considerare se sintomatici".
- why_it_matters: one or two sentences. First what the source adds, then where
  it can be relevant in family pediatrics. Do NOT deduce consequences the source
  does not support.
  FORBIDDEN PHRASE: never write "In pratica, questo significa". It is a filler
  formula that turns an observation into an instruction. Write what the source
  shows, then where it may matter, in plain clinical language.
- implication_kind: choose honestly from
  * changes_practice - a guideline or institutional instruction that really changes something
  * worth_attention  - consolidated evidence that reinforces attention to something
  * may_consider     - it may be useful to bear in mind in certain situations
  * no_change        - interesting, but does not by itself modify practice
  * insufficient     - the evidence does not yet allow operational indications
- what_to_do: AT MOST ONE short practical implication, and ONLY when
  implication_kind is changes_practice, worth_attention or may_consider.
  Leave it EMPTY for no_change and insufficient.
  Imperatives such as ricontrolla, invia, modifica, mantieni, monitora and
  prescrivi require a source that justifies them: use them for guidelines and
  institutional documents, not for a single observational study.
  Never audit the reader ("Verifica se le tue pratiche sono allineate").

LANGUAGE MUST MATCH THE STRENGTH OF THE EVIDENCE:
- Guideline or clear institutional instruction: a direct operational wording is allowed.
- Systematic review or consolidated evidence: clinical implications allowed, with
  their limits and population stated.
- Observational study: describe the association and its possible relevance.
  Do not turn it into a clinical indication. Prefer wordings that keep the
  uncertainty ("si associa a", "e' stata osservata", "potrebbe essere rilevante").
  For an observational study implication_kind may be AT MOST may_consider, and
  the title must not contain a recommendation.
- Preliminary or single study: present it as something to know or follow.
- Incomplete or inaccessible document: make no recommendation at all.

- summary: 2 to 5 lines giving what the reader needs to decide whether to go
  deeper. Specifics over adjectives: ages, doses, dates, thresholds. No filler
  openers. Do not restate the headline or why_it_matters in other words.
- source_note: max {SOURCE_NOTE_MAX_CHARS} characters naming what kind of source this is and
  what it does NOT let you conclude, for example "Studio osservazionale. Mostra
  associazioni, non consente indicazioni operative." Never a bare grade.
- Ground every claim in the numbered EVIDENCE passages. Cite the passage number
  in supporting_passage_ref (for example "P2").
- Keep separate what the source states, what may be relevant for a PLS, and what
  follows in practice. Never attribute a recommendation to a source whose full
  text you have not read. Never turn an association into causality.
- If ACCESS LIMITED is true this is a document notice, not a clinical
  recommendation. Say plainly that the full text is reserved, set
  implication_kind to insufficient, leave what_to_do empty, and make sure the
  headline does not imply a change in practice.
- Never write a therapeutic protocol unless the source is a national guideline
  or consensus document."""


class SynthesisCitation(BaseModel):
    claim_id: str
    source_url: str
    supporting_passage_ref: str = ""


class SynthesisResponse(BaseModel):
    headline_operational: str
    why_it_matters: str
    implication_kind: ImplicationKind = ImplicationKind.WORTH_ATTENTION
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
            implication_kind=ImplicationKind.INSUFFICIENT,
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

    actions = [a.strip() for a in resp.what_to_do if a.strip()][:MAX_ACTIONS]
    # A conclusion of "nothing changes" must not arrive with an action attached.
    if resp.implication_kind in NO_ACTION_KINDS:
        actions = []

    return EditorialBlock(
        headline_operational=resp.headline_operational.strip()[:HEADLINE_MAX_CHARS],
        why_it_matters=resp.why_it_matters.strip(),
        implication_kind=resp.implication_kind,
        what_to_do=actions,
        summary=resp.summary.strip(),
        source_note=resp.source_note.strip()[:SOURCE_NOTE_MAX_CHARS],
        confidence=confidence,
        citations=citations,
    )
