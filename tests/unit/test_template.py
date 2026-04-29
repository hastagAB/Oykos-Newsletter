"""Tests for HTML/text template rendering - S023."""
from __future__ import annotations

from uuid import uuid4

from oykos.models.news_item import (
    EditorialBlock,
    IssueMetrics,
    Newsletter,
    NewsletterSlot,
)
from oykos.models.taxonomy import Confidence, IssueStatus, Section
from oykos.newsletter.template import render_html, render_plain_text


def _make_newsletter() -> Newsletter:
    return Newsletter(
        issue_id=uuid4(),
        week="2026-W18",
        status=IssueStatus.DRAFT,
        slots=[
            NewsletterSlot(
                position=1,
                section=Section.TOP_PRIORITY,
                item_id=uuid4(),
                editorial=EditorialBlock(
                    headline_operational="AIFA: nuovo avviso sicurezza paracetamolo",
                    why_it_matters="Impatto diretto sulla prescrizione pediatrica.",
                    what_to_do=["Verificare scorte", "Informare i genitori"],
                    confidence=Confidence.HIGH,
                ),
            ),
            NewsletterSlot(
                position=2,
                section=Section.CLINICAL,
                item_id=uuid4(),
                editorial=EditorialBlock(
                    headline_operational="Nuova linea guida bronchiolite SIP",
                    why_it_matters="Aggiornamento criteri di ricovero.",
                    what_to_do=["Rivedere protocollo", "Aggiornare triage"],
                    confidence=Confidence.MEDIUM,
                ),
            ),
        ],
        metrics=IssueMetrics(italy_count=2, foreign_count=0),
    )


def test_render_html_contains_title() -> None:
    nl = _make_newsletter()
    html = render_html(nl)
    # Jinja2 autoescape converts ' to &#39;
    assert "Essenziale in Pediatria" in html
    assert "2026-W18" in html


def test_render_html_contains_items() -> None:
    nl = _make_newsletter()
    html = render_html(nl)
    assert "paracetamolo" in html
    assert "bronchiolite" in html


def test_render_html_contains_actions() -> None:
    nl = _make_newsletter()
    html = render_html(nl)
    assert "Verificare scorte" in html


def test_render_html_contains_confidence_badges() -> None:
    nl = _make_newsletter()
    html = render_html(nl)
    assert "confidence-high" in html
    assert "confidence-medium" in html


def test_render_plain_text_basic() -> None:
    nl = _make_newsletter()
    text = render_plain_text(nl)
    assert "paracetamolo" in text
    assert "bronchiolite" in text
    assert "2026-W18" in text


def test_render_html_empty_newsletter() -> None:
    nl = Newsletter(week="2026-W18", status=IssueStatus.DRAFT, metrics=IssueMetrics())
    html = render_html(nl)
    assert "2026-W18" in html
