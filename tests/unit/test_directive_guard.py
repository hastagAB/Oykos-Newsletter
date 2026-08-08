"""Tests for the directive guard - editorial feedback of 2026-08-08.

The reviewer's test is simple and concrete: some articles must be able to end
with no "Cosa fare ora" and no imperative addressed to the pediatrician. A
prompt instruction did not achieve that twice running, so the rule is enforced
in code and asserted here.
"""
from __future__ import annotations

import pytest

from oykos.llm.synthesis import DIRECTIVE_DOCUMENT_TYPES, _is_directive  # noqa: PLC2701
from oykos.models.taxonomy import DocumentType


@pytest.mark.parametrize(
    "text",
    [
        "Ricontrolla, prima di prescrivere, l'anamnesi di meningioma",
        "Ricontrollare l'anamnesi prima della prescrizione",
        "Invia allo specialista i casi sospetti",
        "Mantieni la pratica attuale",
        "Monitora i sintomi respiratori",
        "Modifica la soglia di invio",
        "Tenere presente un possibile profilo respiratorio",
        "Considera la spirometria nei sintomatici",
        "Abbassa la soglia di sospetto",
        "Non usare questi medicinali in presenza di meningioma",
    ],
)
def test_directive_wording_is_recognised(text: str) -> None:
    assert _is_directive(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Il dato riguarda soprattutto i nati molto pretermine",
        "L'associazione è stata osservata a circa 5 anni",
        "Elemento utile al ragionamento clinico in eta' prescolare",
        "Nei bambini con sintomi ricorrenti la funzione polmonare può essere alterata",
    ],
)
def test_descriptive_wording_is_not_directive(text: str) -> None:
    assert _is_directive(text) is False


def test_only_institutional_sources_may_direct_the_reader() -> None:
    """Section 7: a guideline may be operational, a study may not."""
    assert DocumentType.GUIDELINE in DIRECTIVE_DOCUMENT_TYPES
    assert DocumentType.CONSENSUS in DIRECTIVE_DOCUMENT_TYPES
    assert DocumentType.SAFETY_COMMUNICATION in DIRECTIVE_DOCUMENT_TYPES

    assert DocumentType.STUDY not in DIRECTIVE_DOCUMENT_TYPES
    assert DocumentType.NEWS not in DIRECTIVE_DOCUMENT_TYPES
    assert DocumentType.SURVEILLANCE_REPORT not in DIRECTIVE_DOCUMENT_TYPES
