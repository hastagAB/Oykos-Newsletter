"""Tests for A/B variant selection - guidelines section 11.

The rule is "change only one element at a time". These tests exist because the
first implementation accepted AB_ELEMENT=cta and then silently sent everyone the
same email: a report would have shown an A/B split between two identical groups,
which is worse than no test at all.
"""
from __future__ import annotations

import pytest

from oykos.models.news_item import Newsletter
from oykos.newsletter.subject import SubjectLines
from oykos.newsletter.template import CTA_TITLE, render_html, render_plain_text
from oykos.pipeline.weekly import _variant


@pytest.fixture
def newsletter() -> Newsletter:
    return Newsletter(
        week="2026-W32",
        subject_line="Oggetto A",
        preheader="Preheader A",
    )


@pytest.mark.parametrize("element", ["subject", "preheader", "cta"])
def test_group_b_gets_the_variant_for_the_tested_element(newsletter, element: str) -> None:
    newsletter.ab_element = element
    newsletter.ab_variant_b = "Variante B"

    assert _variant(newsletter, "B", element, "Variante A") == "Variante B"


@pytest.mark.parametrize("element", ["subject", "preheader", "cta"])
def test_group_a_never_sees_the_variant(newsletter, element: str) -> None:
    newsletter.ab_element = element
    newsletter.ab_variant_b = "Variante B"

    assert _variant(newsletter, "A", element, "Variante A") == "Variante A"


def test_only_the_tested_element_varies(newsletter) -> None:
    """Testing the subject must not also change the preheader or the CTA."""
    newsletter.ab_element = "subject"
    newsletter.ab_variant_b = "Oggetto B"

    assert _variant(newsletter, "B", "subject", "Oggetto A") == "Oggetto B"
    assert _variant(newsletter, "B", "preheader", "Preheader A") == "Preheader A"
    assert _variant(newsletter, "B", "cta", "CTA A") == "CTA A"


def test_empty_variant_falls_back_rather_than_blanking_the_email(newsletter) -> None:
    newsletter.ab_element = "cta"
    newsletter.ab_variant_b = ""

    assert _variant(newsletter, "B", "cta", "CTA A") == "CTA A"


def test_cta_title_override_reaches_the_html(newsletter) -> None:
    """Regression: the CTA variant was generated but never passed to the render."""
    html = render_html(newsletter, cta_title="Provalo questa settimana")

    assert "Provalo questa settimana" in html
    assert CTA_TITLE not in html


def test_cta_title_override_reaches_the_plain_text(newsletter) -> None:
    text = render_plain_text(newsletter, cta_title="Provalo questa settimana")

    assert "Provalo questa settimana" in text
    assert CTA_TITLE not in text


def test_default_cta_title_is_used_when_no_variant(newsletter) -> None:
    assert CTA_TITLE in render_html(newsletter)
    assert CTA_TITLE in render_plain_text(newsletter)


def test_variant_for_returns_the_matching_element() -> None:
    lines = SubjectLines(
        subject="A",
        preheader="P",
        subject_b="SB",
        preheader_b="PB",
        cta_b="CB",
    )

    assert lines.variant_for("subject") == "SB"
    assert lines.variant_for("preheader") == "PB"
    assert lines.variant_for("cta") == "CB"


def test_variant_for_none_is_empty_so_no_test_runs() -> None:
    lines = SubjectLines(subject="A", preheader="P", subject_b="SB")

    assert lines.variant_for("none") == ""
