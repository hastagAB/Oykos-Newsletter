"""Editorial QA - the checklist from guidelines v2.0 section 12, run by a model.

Asked for in the editorial feedback of 2026-08-08: check the issue against the
guidelines before it is sent, rather than discovering the drift after a reviewer
reads it.

This does not gate delivery. It produces findings for the review workbench,
because the last check in the checklist is a human one.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import Newsletter

logger = logging.getLogger(__name__)

MAX_ISSUE_CHARS = 12000

QA_SYSTEM = """You audit an Italian pediatric newsletter against its editorial
guidelines. You are the last reader before an editor, and you are looking for
drift back towards a prescriptive register.

THE GUIDELINES, in short. The reader is a Pediatra di Libera Scelta. The
newsletter selects what deserves attention and explains its relevance. The
sequence is NOT "new evidence, therefore do something". It is: what the source
shows, how much it matters, and what changes IF anything changes. An item that
concludes nothing changes is a valid and welcome outcome.

Check each item and report every violation you find:

1. TITLE. Does it describe what we know, or does it embed a recommendation the
   source does not contain? "Ex very preterm: spirometria da considerare se
   sintomatici" is WRONG for an observational study. "Ex very preterm:
   frequenti alterazioni spirometriche in eta' prescolare" is right.
2. LANGUAGE VS EVIDENCE. Is the wording more confident than the source? An
   observational study may describe associations, never issue instructions.
   A guideline or institutional safety communication may be operational.
3. IMPERATIVES. Verbs addressing the pediatrician - ricontrolla, invia,
   modifica, mantieni, monitora, prescrivi, tieni, abbassa la soglia - require
   a source that justifies them. Flag every one that does not.
   These conclusions are EXPLICITLY PERMITTED by the guidelines and must NOT be
   flagged, whatever the source: "Il dato rafforza l'attenzione verso ...",
   "Puo' essere utile tenerne conto quando ...", "E' un elemento da considerare
   soprattutto in ...", "Il dato e' interessante, ma non modifica da solo la
   pratica", "Al momento non emergono indicazioni operative", "L'evidenza non e'
   sufficiente per modificare la gestione". They are contextualisation, not
   instruction.
   An institutional source - a regulator, a national society, a guideline - MAY
   carry operational measures. Reporting what AIFA instructs is not the
   newsletter over-claiming.
4. AUTOMATIC FORMULAS. "In pratica, questo significa", "Cosa fare ora", and any
   phrasing that exists to fill a section rather than to say something.
5. INTERNAL CONSISTENCY. Does the item describe the source prudently and then
   draw a prescriptive conclusion? That contradiction is a serious finding.
6. FORCED ACTION. Is an action proposed only because the layout has room for
   one?
7. SEPARATION. Is it clear what the source states, what may be relevant, and
   what is Oykos's own reading?
8. SUBJECT AND PREHEADER SCOPE. These cover the whole issue, so they must not
   generalise one item's conclusion to the rest. If a single regulatory notice
   changes practice while the other items are observational, naming the source
   ("Nuove indicazioni AIFA su ...") is CORRECT and must not be flagged;
   framing the issue as "cosa cambia questa settimana" is a finding, because it
   misrepresents the items that change nothing.

For every finding give: the item title, what is wrong, the exact offending
text, and a concrete Italian rewrite. Be specific and quote the text.

verdict: "pass" only if a demanding editor would send this issue unchanged.
"needs_work" if any item is more prescriptive than its source supports."""


class Finding(BaseModel):
    item_title: str = ""
    rule: str = ""
    offending_text: str = ""
    why: str = ""
    suggested_rewrite: str = ""


class QAReport(BaseModel):
    verdict: str = "needs_work"
    findings: list[Finding] = Field(default_factory=list)
    prescriptive_items: int = 0
    items_without_action: int = 0
    summary: str = ""

    @property
    def passed(self) -> bool:
        return self.verdict.strip().lower() == "pass"


def _render_for_audit(newsletter: Newsletter) -> str:
    parts: list[str] = [f"Oggetto: {newsletter.subject_line}"]
    if newsletter.preheader:
        parts.append(f"Anteprima: {newsletter.preheader}")
    for slot in newsletter.slots:
        editorial = slot.editorial
        parts.append(
            f"\n--- ITEM {slot.position} [{slot.section.value}] ---\n"
            f"Tipo di fonte: {slot.source_name}\n"
            f"Implicazione dichiarata: {editorial.implication_kind.value}\n"
            f"Titolo: {editorial.headline_operational}\n"
            f"Perche': {editorial.why_it_matters}\n"
            f"Implicazione pratica: "
            f"{' | '.join(editorial.what_to_do) if editorial.what_to_do else '(nessuna)'}\n"
            f"Sintesi: {editorial.summary}\n"
            f"Fonte e limiti: {editorial.source_note}",
        )
    return "\n".join(parts)[:MAX_ISSUE_CHARS]


async def audit_issue(newsletter: Newsletter, client: LLMClient) -> QAReport:
    """Audit a composed issue against the editorial guidelines."""
    if not newsletter.slots:
        return QAReport(verdict="pass", summary="Nessun contenuto da controllare.")

    prompt = f"""Audit this issue against the editorial guidelines.

{_render_for_audit(newsletter)}"""

    try:
        report = await client.complete_structured(
            prompt=prompt,
            response_model=QAReport,
            system=QA_SYSTEM,
        )
    except Exception:
        logger.exception("Editorial QA failed")
        return QAReport(verdict="unknown", summary="Controllo editoriale non riuscito.")

    report.items_without_action = sum(
        1 for slot in newsletter.slots if not slot.editorial.what_to_do
    )
    logger.info(
        "Editorial QA: %s, %d finding(s), %d item(s) without an action",
        report.verdict, len(report.findings), report.items_without_action,
    )
    for finding in report.findings:
        logger.warning(
            "QA [%s] %.50s: %.90s",
            finding.rule, finding.item_title, finding.offending_text,
        )
    return report
