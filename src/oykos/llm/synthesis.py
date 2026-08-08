"""Editorial synthesis - S019.

Produces the 5-block item template of the blueprint (Section 5) from the
evidence passages extracted in S018. The model never sees the raw document as
its only input: claims must be traceable to a numbered passage.
"""
from __future__ import annotations

import hashlib
import logging
import re

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import Citation, EditorialBlock, NewsItem
from oykos.models.taxonomy import Confidence, DocumentType, ImplicationKind

logger = logging.getLogger(__name__)

HEADLINE_MAX_CHARS = 90
SOURCE_NOTE_MAX_CHARS = 140
MAX_ACTIONS = 1
MAX_FALLBACK_SUMMARY_CHARS = 500

# Conclusions that are complete without an action.
NO_ACTION_KINDS = frozenset({ImplicationKind.NO_CHANGE, ImplicationKind.INSUFFICIENT})

# Section 7: only a guideline or a clear institutional instruction justifies a
# direct operational formulation. Everything else describes, it does not direct.
DIRECTIVE_DOCUMENT_TYPES = frozenset({
    DocumentType.GUIDELINE,
    DocumentType.CONSENSUS,
    DocumentType.SAFETY_COMMUNICATION,
    DocumentType.LEGAL_UPDATE,
})

# A regulator speaks with institutional authority whatever the classifier called
# the page. Without this an AIFA safety notice was demoted to "non modifica la
# pratica", which understates a real safety signal.
INSTITUTIONAL_RELIABILITY = 5

# Kinds a study may not claim: an observational finding is not a change in practice.
STUDY_MAX_KINDS = frozenset({
    ImplicationKind.MAY_CONSIDER,
    ImplicationKind.NO_CHANGE,
    ImplicationKind.INSUFFICIENT,
})

# Verbs that address the pediatrician directly, in imperative or infinitive.
# The editorial feedback of 2026-08-08 objected to exactly these.
_DIRECTIVE_VERB = re.compile(
    # Both stems where Italian changes them: mantenere -> mantieni, tenere -> tieni.
    r"\b(?:non\s+)?(?:ricontroll|controll|verific|invi|modific|manten|mantien|"
    r"monitor|prescriv|tien|tenere|consider|valut|applic|adott|utilizz|"
    r"us(?:a|are|ando)|riduc|abbass|alz|aument|segnal|ricord|inform|chied|"
    r"esegu)\w*\b",
    re.IGNORECASE,
)


def _is_directive(text: str) -> bool:
    """Whether the text tells the reader to do something."""
    return bool(_DIRECTIVE_VERB.match(text.strip()))


# Section 10 lists the conclusions a non-institutional source may carry. Anything
# else - including impersonal steering like "Da tenere presente nel follow-up" -
# reads as an instruction the evidence does not support.
_SANCTIONED_OPENING = re.compile(
    r"^\s*(?:"
    r"il\s+dato\s+rafforza\s+l['’]attenzione"
    r"|può\s+essere\s+utile\s+tenerne\s+conto"
    r"|è\s+un\s+elemento\s+da\s+considerare"
    r"|il\s+dato\s+è\s+interessante"
    r"|al\s+momento\s+non\s+emergono"
    r"|l['’]evidenza\s+non\s+è\s+sufficiente"
    r"|questo\s+aggiornamento\s+modifica"
    r")",
    re.IGNORECASE,
)


def _is_sanctioned_conclusion(text: str) -> bool:
    return bool(_SANCTIONED_OPENING.match(text))


def rules_version() -> str:
    """Fingerprint of the editorial rules that produced a piece of copy.

    Editorial copy is cached, so changing the guidelines used to leave the
    published text untouched until someone remembered to force a rewrite. That
    was missed three times. Copy now carries the fingerprint of the rules that
    wrote it, and anything stale is regenerated without being asked.
    """
    material = SYNTHESIS_SYSTEM + "|".join(sorted(k.value for k in ImplicationKind))
    return hashlib.sha256(material.encode()).hexdigest()[:12]

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

  IF THE SOURCE IS NOT A GUIDELINE OR AN INSTITUTIONAL DOCUMENT, the implication
  must begin with one of these exact forms and nothing else:
    "Il dato rafforza l'attenzione verso ..."
    "Puo' essere utile tenerne conto quando ..."
    "E' un elemento da considerare soprattutto in ..."
  Anything else is dropped. In particular do NOT write "Da tenere presente
  nel ...", "Tema da tenere presente ...", "Utile ricordare ...": these steer
  behaviour without naming anyone, and an observational study does not support
  steering behaviour.

  For a guideline or institutional document you may write a direct operational
  sentence, but it must be ATTRIBUTED to the source, not issued by us. Write
  "AIFA indica di non utilizzare ..." or "La nota informativa raccomanda di
  ...", never a bare "Non utilizzare ..." that reads as the newsletter
  instructing the pediatrician.
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
    kind = resp.implication_kind

    # Section 7, enforced rather than requested. A study describes; it does not
    # instruct. The model keeps reaching for an imperative, so the rule lives
    # here where wording cannot get around it.
    directive_allowed = (
        item.content.document_type in DIRECTIVE_DOCUMENT_TYPES
        or item.source.reliability_tier >= INSTITUTIONAL_RELIABILITY
    )
    if not directive_allowed:
        if kind is ImplicationKind.CHANGES_PRACTICE:
            kind = ImplicationKind.MAY_CONSIDER
        # A non-institutional source may only conclude in one of the forms the
        # guidelines list, and may not open with an imperative. "Da tenere
        # presente nel follow-up" steers behaviour without addressing anyone,
        # so it slipped past the verb check on its own.
        if actions and (
            not _is_sanctioned_conclusion(actions[0]) or _is_directive(actions[0])
        ):
            logger.info(
                "Dropped unsanctioned implication on a non-institutional source: %.60s",
                actions[0],
            )
            actions = []
            kind = ImplicationKind.NO_CHANGE

    if item.content.document_type is DocumentType.STUDY and kind not in STUDY_MAX_KINDS:
        kind = ImplicationKind.MAY_CONSIDER

    # A conclusion of "nothing changes" must not arrive with an action attached.
    if kind in NO_ACTION_KINDS:
        actions = []

    return EditorialBlock(
        headline_operational=resp.headline_operational.strip()[:HEADLINE_MAX_CHARS],
        why_it_matters=resp.why_it_matters.strip(),
        implication_kind=kind,
        what_to_do=actions,
        rules_version=rules_version(),
        summary=resp.summary.strip(),
        source_note=resp.source_note.strip()[:SOURCE_NOTE_MAX_CHARS],
        confidence=confidence,
        citations=citations,
    )
