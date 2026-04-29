"""Tests for alert template rendering - S033."""
from __future__ import annotations

from oykos.alerts.template import render_alert_html, render_alert_text
from oykos.alerts.triggers import AlertLevel
from oykos.models.news_item import EditorialBlock
from oykos.models.taxonomy import Confidence


def _make_editorial() -> EditorialBlock:
    return EditorialBlock(
        headline_operational="AIFA ritira lotto paracetamolo pediatrico",
        why_it_matters="Rischio contaminazione nel lotto AB1234.",
        what_to_do=["Controllare scorte in ambulatorio", "Avvisare genitori"],
        summary="L'AIFA ha disposto il ritiro cautelativo del lotto.",
        confidence=Confidence.HIGH,
    )


def test_render_alert_html_critical() -> None:
    html = render_alert_html(AlertLevel.CRITICAL, _make_editorial())
    assert "ALLERTA CRITICA" in html
    assert "paracetamolo" in html
    assert "#c0392b" in html  # Red color


def test_render_alert_html_high() -> None:
    html = render_alert_html(AlertLevel.HIGH, _make_editorial())
    assert "ALLERTA ALTA" in html


def test_render_alert_html_medium() -> None:
    html = render_alert_html(AlertLevel.MEDIUM, _make_editorial())
    assert "AVVISO" in html


def test_render_alert_text_critical() -> None:
    text = render_alert_text(AlertLevel.CRITICAL, _make_editorial())
    assert "ALLERTA CRITICA" in text
    assert "paracetamolo" in text
    assert "Controllare scorte" in text


def test_render_alert_text_contains_actions() -> None:
    text = render_alert_text(AlertLevel.CRITICAL, _make_editorial())
    assert "Cosa fare:" in text
    assert "Avvisare genitori" in text
