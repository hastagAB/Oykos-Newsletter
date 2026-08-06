"""A members-only source must be visibly marked before the reader clicks.

Editorial guidelines section 8 reports such documents rather than hiding them,
and the pre-publication checklist requires that "il link promette esattamente
cio che il lettore trovera".
"""
from __future__ import annotations

from datetime import UTC, datetime

from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import Confidence, DocumentType, Geo, TaxonomyTag
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.template import render_html, render_plain_text

WEEK = "2026-W17"
IN_WEEK = datetime.fromisocalendar(2026, 17, 3).replace(tzinfo=UTC)
BADGE = "ACCESSO RISERVATO AI SOCI"


def _item(*, access_limited: bool) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key="sicupp",
            name="SICuPP",
            source_type="scrape",
            country="IT",
            reliability_tier=4,
        ),
        content=ContentBlock(
            title="Gestione dell'attacco acuto di asma",
            canonical_url="https://sicupp.org/linee-guida-commentate/asma",
            published_at=IN_WEEK,
            document_type=DocumentType.GUIDELINE,
            access_limited=access_limited,
        ),
        classification=Classification(geo=Geo.IT, taxonomy_tags=[TaxonomyTag.RESPIRATORY]),
        scoring=ScoringBlock(
            score_total=90,
            subscores=Subscores(
                pls_relevance=5,
                clinical_impact=4,
                operational_impact=4,
                source_trust=5,
                novelty=4,
                actionability=4,
                urgency=2,
            ),
        ),
        editorial=EditorialBlock(
            headline_operational="Attacco acuto d'asma: per ora non cambiare la pratica",
            why_it_matters="In pratica, senza il testo integrale non ci sono basi per modificare il triage.",
            what_to_do=["Consulta il documento se hai accesso, altrimenti mantieni la pratica attuale"],
            summary="Segnalazione di documento.",
            source_note="Documento associativo. Testo integrale riservato ai soci.",
            confidence=Confidence.LOW,
        ),
    )


def test_members_only_source_is_marked_before_the_link() -> None:
    newsletter = compose_newsletter([_item(access_limited=True)], WEEK)

    assert newsletter.slots[0].access_limited
    assert BADGE in render_html(newsletter)
    assert "Accesso riservato ai soci" in render_plain_text(newsletter)


def test_open_source_carries_no_restriction_badge() -> None:
    newsletter = compose_newsletter([_item(access_limited=False)], WEEK)

    assert not newsletter.slots[0].access_limited
    assert BADGE not in render_html(newsletter)
