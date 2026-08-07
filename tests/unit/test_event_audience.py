"""Tests for the PLS federation audience rule.

The editorial feedback pulls in two directions: section 6.3 forbids inferring
relevance from the promoting society's name, while the worked example in 6.4
expects Children 2026, a national FIMP event, to appear. FIMP is the federation
OF family pediatricians, so its own events have a PLS audience by constitution.
This is a named list of PLS organisations, not a general society-name rule.
"""
from __future__ import annotations

import pytest

from oykos.events.extractor import ExtractedEvent, to_event
from oykos.events.models import PLSFit

PAGE = "https://www.fimp.pro/eventi/prossimi-eventi"


def _raw(**overrides: object) -> ExtractedEvent:
    base: dict[str, object] = {
        "title": "Children 2026",
        "start_date": "2026-09-04",
        "pls_fit": "unsupported",
    }
    base.update(overrides)
    return ExtractedEvent(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize("acronym", ["FIMP", "SIMPeF", "ACP", "SIMPE"])
def test_pls_federation_event_gets_an_explicit_audience(acronym: str) -> None:
    event = to_event(_raw(), "SRC005", PAGE, acronym)

    assert event is not None
    assert event.pls_fit is PLSFit.EXPLICIT


def test_the_upgrade_is_recorded_as_evidence() -> None:
    """An editor must be able to see why the audience was accepted."""
    event = to_event(_raw(), "SRC005", PAGE, "FIMP")

    assert event is not None
    assert any("statuto" in line for line in event.programme_evidence)


def test_other_societies_are_not_upgraded() -> None:
    """A hospital or subspecialist society name proves nothing about PLS fit."""
    for acronym in ("SIGENP", "SIMRI", "SINPIA", "SIP"):
        event = to_event(_raw(), "SRC099", PAGE, acronym)

        assert event is not None
        assert event.pls_fit is PLSFit.UNSUPPORTED


def test_an_explicit_audience_is_never_downgraded() -> None:
    event = to_event(_raw(pls_fit="explicit", stated_audience="PLS"), "SRC005", PAGE, "SIGENP")

    assert event is not None
    assert event.pls_fit is PLSFit.EXPLICIT


def test_the_hard_rule_still_applies_to_federation_events() -> None:
    """No start date means no event, whoever is promoting it."""
    assert to_event(_raw(start_date=""), "SRC005", PAGE, "FIMP") is None


def test_promoter_on_the_page_also_triggers_the_rule() -> None:
    event = to_event(_raw(promoter="Federazione Italiana Medici Pediatri FIMP"), "SRC099", PAGE)

    assert event is not None
    assert event.pls_fit is PLSFit.EXPLICIT
