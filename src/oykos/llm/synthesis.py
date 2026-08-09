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


def is_directive(text: str) -> bool:
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


def is_sanctioned_conclusion(text: str) -> bool:
    return bool(_SANCTIONED_OPENING.match(text))


# Section 6: open with the message, not with the bibliography. The source type
# is already carried by source_note, so this only costs the most read line.
_BIBLIOGRAPHIC_OPENING = re.compile(
    r"^\s*(?:questo|questa|lo|la|il|un|una|nel|nello)\s+"
    r"(?:recente\s+|nuovo\s+|nuova\s+|ampio\s+|ampia\s+)?"
    r"(?:studio|revisione|ricerca|articolo|lavoro|analisi|indagine|documento|report)\b",
    re.IGNORECASE,
)


def opens_with_bibliography(text: str) -> bool:
    return bool(_BIBLIOGRAPHIC_OPENING.match(text))


def _normalise_quotes(text: str) -> str:
    """One apostrophe shape per issue; the model mixes U+2019 with U+0027."""
    return text.replace("\u2019", "'").replace("\u2018", "'")


# The model imitates whatever apostrophe style it is shown and drifts into
# ASCII fallbacks. Unaccented Italian reads as misspelled to the audience, so it
# is repaired here rather than asked for and hoped.
_ASCII_ACCENTS = {
    "e": "è", "piu": "più", "gia": "già", "cio": "ciò", "puo": "può",
    "cosi": "così", "ne": "né", "si": "sì", "la": "là", "li": "lì",
    "perche": "perché", "poiche": "poiché", "benche": "benché",
    "finche": "finché", "affinche": "affinché", "cioe": "cioè",
    "meta": "metà", "eta": "età", "citta": "città", "papa": "papà",
}
_ASCII_TOKEN = re.compile(r"\b([A-Za-zÀ-ÿ]+)'(?![A-Za-zÀ-ÿ])")


def _fix_ascii_accents(text: str) -> str:
    def repair(match: re.Match[str]) -> str:
        word = match.group(1)
        lowered = word.lower()
        # Any noun in -ita' is an accented -ità; "po'" is a real elision.
        if lowered.endswith("ita") and len(lowered) > 4:
            fixed = word[:-3] + "ità"
        elif lowered in _ASCII_ACCENTS:
            fixed = _ASCII_ACCENTS[lowered]
        else:
            return match.group(0)
        return fixed[0].upper() + fixed[1:] if word[0].isupper() else fixed

    return _ASCII_TOKEN.sub(repair, text)


# Asking for Italian did not stop these coming back, so they are translated.
# Only terms with one unambiguous Italian equivalent belong here; screening and
# follow-up are left alone because Italian clinicians use them as such.
_ANGLICISMS = {
    "preparedness": "preparazione clinica",
    "awareness": "consapevolezza",
    "burden": "carico",
    "setting": "contesto",
    "care pathway": "percorso di cura",
}
_ANGLICISM_TOKEN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _ANGLICISMS) + r")\b",
    re.IGNORECASE,
)


def _translate_anglicisms(text: str) -> str:
    def swap(match: re.Match[str]) -> str:
        italian = _ANGLICISMS[match.group(0).lower()]
        return italian.capitalize() if match.group(0)[0].isupper() else italian

    return _ANGLICISM_TOKEN.sub(swap, text)


def _clean_text(text: str) -> str:
    return _translate_anglicisms(_fix_ascii_accents(_normalise_quotes(text)))


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
- Write in Italian with correct accents. NEVER use the ASCII fallbacks
  perche' piu' gia' cio' eta' e'. Always write perché, più, già, ciò, età, è,
  qualità, criticità, attività. Unaccented Italian reads as misspelled to an
  Italian physician.
- Write in Italian throughout. Do not leave English terms untranslated when
  Italian has an equivalent: write "preparazione clinica" not "preparedness",
  "contesto" or "ambito" not "setting", "percorso di cura" not "care pathway".
  Keep only terms Italian clinicians genuinely use as such (screening, follow-up,
  case report, drop-out).
- headline_operational: max {HEADLINE_MAX_CHARS} characters. Informative before
  catchy. It must describe WHAT WE KNOW, and may carry a consequence only when
  the source genuinely supports one. Never put a recommendation in the title
  that the source does not contain.
  For an observational study showing an association, write
  "Ex very preterm: frequenti alterazioni spirometriche in età prescolare",
  NOT "Ex very preterm: spirometria da considerare se sintomatici".
- what_emerges: one or two sentences saying what the source actually adds.

  OPEN WITH THE FINDING, NEVER WITH THE BIBLIOGRAPHY. Do not begin with
  "Questo studio ...", "Lo studio ...", "Un recente studio ...", "Questa
  revisione ...", "L'articolo ...", "La ricerca ...". The kind of source is
  already stated in source_note, so naming it here wastes the first and most
  read line on nothing.
  WRONG:   "Questo studio trasversale su bambini di 4-5 anni osserva
            un'associazione tra esposizione agli schermi e disturbi del sonno."
  RIGHT:   "In età prescolare un tempo di schermo prolungato e l'uso serale
            dei media si associano a più disturbi del sonno."

  STATE THE FINDING, NOT THE MEASURE. What the source instructs belongs in
  what_to_do and must not also appear here, or the reader is told the same
  thing twice in two blocks. Write "AIFA segnala un aumento del rischio di
  meningioma con uso prolungato" and leave "non utilizzare in caso di
  meningioma" to the implication.
- why_it_matters: one or two sentences on where this can be relevant in family
  pediatrics, and for which children. Do NOT repeat what_emerges in other words
  and do NOT deduce consequences the source does not support.
  It must not overlap the implication either: this block says WHERE the topic
  is relevant, the implication says WHAT follows from it.
  FORBIDDEN PHRASE: never write "In pratica, questo significa". It is a filler
  formula that turns an observation into an instruction.- implication_kind: choose honestly from
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
    "Può essere utile tenerne conto quando ..."
    "È un elemento da considerare soprattutto in ..."
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
  uncertainty ("si associa a", "è stata osservata", "potrebbe essere rilevante").
  For an observational study implication_kind may be AT MOST may_consider, and
  the title must not contain a recommendation.
- Preliminary or single study: present it as something to know or follow.
- Incomplete or inaccessible document: make no recommendation at all.

- summary: 2 to 5 lines giving what the reader needs to decide whether to go
  deeper. Specifics over adjectives: ages, doses, dates, thresholds. No filler
  openers. It must ADD to the blocks above, never restate them: do not repeat
  the headline, what_emerges, why_it_matters or the implication in other words.
  If the only thing left to say is what has already been said, write less.
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
    what_emerges: str = ""
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
            not is_sanctioned_conclusion(actions[0]) or is_directive(actions[0])
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

    what_emerges = _clean_text(resp.what_emerges.strip())
    why_it_matters = _clean_text(resp.why_it_matters.strip())

    # Cannot be rewritten safely without destroying the sentence, so it is
    # surfaced to the editor instead of being silently shipped.
    if what_emerges and opens_with_bibliography(what_emerges):
        logger.warning(
            "Bibliographic opening kept for review: %.70s", what_emerges,
        )

    return EditorialBlock(
        headline_operational=_clean_text(
            resp.headline_operational.strip()[:HEADLINE_MAX_CHARS],
        ),
        what_emerges=what_emerges,
        why_it_matters=why_it_matters,
        implication_kind=kind,
        what_to_do=[_clean_text(a) for a in actions],
        rules_version=rules_version(),
        summary=_clean_text(resp.summary.strip()),
        source_note=_clean_text(resp.source_note.strip()[:SOURCE_NOTE_MAX_CHARS]),
        confidence=confidence,
        citations=citations,
    )
