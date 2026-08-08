"""Tests for the sanctioned-conclusion rule (guidelines v2.0 section 10).

The reviewer objected twice to a prescriptive register. The verb check caught
"Ricontrolla ..." but not "Da tenere presente nel follow-up ...", which steers
behaviour without addressing anyone. Section 10 lists the conclusions a
non-institutional source may carry, so that list is what the code enforces.
"""
from __future__ import annotations

import pytest

from oykos.llm.synthesis import _is_sanctioned_conclusion  # noqa: PLC2701


@pytest.mark.parametrize(
    "text",
    [
        "Il dato rafforza l'attenzione verso il sonno nei prescolari",
        "Il dato rafforza l’attenzione verso il sonno nei prescolari",
        "Può essere utile tenerne conto quando emergono sintomi respiratori",
        "È un elemento da considerare soprattutto in presenza di familiarità atopica",
        "Il dato è interessante, ma non modifica da solo la pratica",
        "Al momento non emergono indicazioni operative",
        "L'evidenza non è sufficiente per modificare la gestione",
    ],
)
def test_section_ten_conclusions_are_accepted(text: str) -> None:
    assert _is_sanctioned_conclusion(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Da tenere presente nel follow-up respiratorio dei prescolari ex very preterm",
        "Tema da tenere presente quando si programmano formazione e contesti di cura",
        "Utile ricordare la storia perinatale nei pretermine",
        "Ricontrolla l'anamnesi prima di prescrivere",
        "Considerare la spirometria nei sintomatici",
        "Opportuno valutare il profilo respiratorio",
    ],
)
def test_steering_without_an_addressee_is_still_refused(text: str) -> None:
    """The register the reviewer objected to, in impersonal form."""
    assert _is_sanctioned_conclusion(text) is False
