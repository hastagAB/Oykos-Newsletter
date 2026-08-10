"""Deterministic compliance check of a composed issue - editorial guidelines v2.0.

The LLM auditor in ``llm.editorial_qa`` is a demanding first reader whose verdict
varies between runs. This module does not ask anyone's opinion: every check here
is a rule from the guidelines expressed as code, so the same issue always gets
the same answer.

It covers what can be decided mechanically. Three checklist items in section 12
are judgements a person has to make, and they are reported as such rather than
being quietly counted as passes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from oykos.llm.synthesis import (
    is_directive,
    is_sanctioned_conclusion,
    opens_with_bibliography,
)
from oykos.models.news_item import Newsletter, NewsletterSlot
from oykos.models.taxonomy import ImplicationKind

HEADLINE_MAX_CHARS = 90
SUBJECT_MAX_CHARS = 60
PREHEADER_MAX_CHARS = 120

# Section 6: forbidden as an automatic scheme.
BANNED_PHRASES = (
    "in pratica, questo significa",
    "cosa fare ora",
    "cosa fare adesso",
)

# Section 2: the audience is Italian. These have ordinary Italian equivalents.
ANGLICISMS = (
    "preparedness",
    "setting",
    "care pathway",
    "awareness",
    "burden",
    "gender-diverse",
)

# Unaccented Italian reads as misspelled to an Italian physician.
ASCII_ACCENT = re.compile(
    r"\b(?:perche|piu|gia|cio|puo|cosi|citta|eta|meta|[a-zà-ÿ]{3,}ita)'(?![a-zà-ÿ])",
    re.IGNORECASE,
)

# Section 9: a title must not carry a recommendation the source does not make.
TITLE_RECOMMENDATION = re.compile(
    r"\b(?:da\s+(?:considerare|valutare|eseguire|evitare|preferire)"
    r"|si\s+raccomanda|raccomandat[oaie]|indicat[oaie]\s+in|obbligatori[oa])\b",
    re.IGNORECASE,
)

INSTITUTIONAL_KINDS = {ImplicationKind.CHANGES_PRACTICE}


@dataclass
class Compliance:
    """The result of checking one issue."""

    failures: list[str] = field(default_factory=list)
    human_checks: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.failures


def _check_item(index: int, slot: NewsletterSlot, out: Compliance) -> None:
    ed = slot.editorial
    where = f"Item {index}"
    text_blocks = {
        "titolo": ed.headline_operational,
        "cosa emerge": ed.what_emerges,
        "perche": ed.why_it_matters,
        "sintesi": ed.summary,
        "fonte e limiti": ed.source_note,
        **{f"implicazione {i}": a for i, a in enumerate(ed.what_to_do, 1)},
    }

    # Section 5: the blocks that must exist.
    if not ed.headline_operational.strip():
        out.failures.append(f"{where}: manca il titolo (sezione 5)")
    if not ed.what_emerges.strip():
        out.failures.append(f"{where}: manca 'cosa emerge' (sezione 5)")
    if not ed.why_it_matters.strip():
        out.failures.append(f"{where}: manca 'perche puo contare per il PLS' (sezione 5)")
    if not ed.source_note.strip():
        out.failures.append(f"{where}: manca 'fonte e limiti' (sezione 11)")

    if len(ed.headline_operational) > HEADLINE_MAX_CHARS:
        out.failures.append(f"{where}: titolo oltre {HEADLINE_MAX_CHARS} caratteri (sezione 9)")

    if TITLE_RECOMMENDATION.search(ed.headline_operational):
        out.failures.append(
            f"{where}: il titolo incorpora una raccomandazione (sezione 9): "
            f"{ed.headline_operational!r}",
        )

    # Section 6: open with the message, not the bibliography.
    if ed.what_emerges and opens_with_bibliography(ed.what_emerges):
        out.failures.append(
            f"{where}: 'cosa emerge' apre con il contesto bibliografico (sezione 6): "
            f"{ed.what_emerges[:60]!r}",
        )

    # Section 6: separate what the source shows from what may be relevant.
    if ed.what_emerges.strip() and ed.what_emerges.strip() == ed.why_it_matters.strip():
        out.failures.append(f"{where}: 'cosa emerge' e 'perche' sono identici (sezione 6)")

    for label, text in text_blocks.items():
        lowered = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lowered:
                out.failures.append(
                    f"{where}: formula vietata in '{label}' (sezione 6): {phrase!r}",
                )
        for word in ANGLICISMS:
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                out.failures.append(f"{where}: anglicismo in '{label}' (sezione 2): {word!r}")
        ascii_accent = ASCII_ACCENT.search(text)
        if ascii_accent:
            out.failures.append(
                f"{where}: accenti ASCII in '{label}': {ascii_accent.group(0)!r}",
            )

    # Section 3: no action attached to a conclusion that nothing changes.
    if ed.implication_kind in {ImplicationKind.NO_CHANGE, ImplicationKind.INSUFFICIENT}:
        if ed.what_to_do:
            out.failures.append(
                f"{where}: implicazione presente con conclusione "
                f"'{ed.implication_kind.value}' (sezione 3)",
            )
        return

    if not ed.what_to_do:
        return

    # Section 7 and 10: who may direct the reader, and in which words.
    institutional = ed.implication_kind in INSTITUTIONAL_KINDS
    for action in ed.what_to_do:
        if institutional:
            # An institutional measure must be attributed, never issued by us.
            if is_directive(action):
                out.failures.append(
                    f"{where}: misura operativa non attribuita alla fonte (sezione 7/11): "
                    f"{action[:70]!r}",
                )
        elif not is_sanctioned_conclusion(action) or is_directive(action):
            out.failures.append(
                f"{where}: conclusione fuori dalle formule ammesse (sezione 10): "
                f"{action[:70]!r}",
            )


def check_issue(newsletter: Newsletter) -> Compliance:
    """Check a composed issue against every rule that can be decided in code."""
    out = Compliance()

    if not newsletter.slots:
        out.failures.append("Il numero non contiene articoli")
        return out

    if len(newsletter.subject_line) > SUBJECT_MAX_CHARS:
        out.failures.append(f"Oggetto oltre {SUBJECT_MAX_CHARS} caratteri (sezione 9)")
    if len(newsletter.preheader) > PREHEADER_MAX_CHARS:
        out.failures.append(f"Anteprima oltre {PREHEADER_MAX_CHARS} caratteri (sezione 4)")

    wrapper = f"{newsletter.subject_line} {newsletter.preheader}".lower()
    for phrase in BANNED_PHRASES:
        if phrase in wrapper:
            out.failures.append(f"Oggetto/anteprima: formula vietata (sezione 6): {phrase!r}")
    if ASCII_ACCENT.search(wrapper):
        out.failures.append("Oggetto/anteprima: accenti ASCII")

    # Section 9.1: the wrapper may not generalise one item's conclusion.
    changing = [
        s for s in newsletter.slots
        if s.editorial.implication_kind is ImplicationKind.CHANGES_PRACTICE
    ]
    if (
        changing
        and len(changing) < len(newsletter.slots)
        and re.search(r"cosa\s+cambia|cosa\s+fare", wrapper)
    ):
        out.failures.append(
            "Oggetto/anteprima: cornice operativa estesa a tutto il numero "
            "mentre solo alcuni item cambiano la pratica (sezione 9.1)",
        )

    # Section 8: nothing is padded to fill a layout.
    bodies = {s.editorial.why_it_matters.strip() for s in newsletter.slots}
    repeated = [line for line in newsletter.tldr if line.strip() in bodies]
    if repeated:
        out.failures.append(
            f"Apertura: {len(repeated)} riga/e ripetono testualmente il corpo dell'articolo "
            "(sezione 8)",
        )

    for index, slot in enumerate(newsletter.slots, start=1):
        _check_item(index, slot, out)

    out.human_checks = [
        "Un pediatra riconoscerebbe il ragionamento clinico come naturale? (sezione 12)",
        "Il contenuto offre valore anche senza aprire il link? (sezione 12)",
        "La validazione clinica finale e' stata completata? (sezione 12)",
    ]
    return out
