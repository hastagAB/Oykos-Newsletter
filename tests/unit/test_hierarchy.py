"""Editorial hierarchy: the week's priority is developed, the rest stay compact.

Guidelines section 7.1: "Not all updates need to receive the same space. The
length should reflect the impact on practice... No content should be stretched
just to fill a set graphic structure."
"""
from __future__ import annotations

from datetime import UTC, datetime

from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    KeyPassage,
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

PRIORITY_SUMMARY = "Approfondimento esteso riservato alla priorita della settimana."
SECONDARY_SUMMARY = "Dettaglio secondario che non deve occupare spazio da priorita."
PRIORITY_QUOTE = (
    "La saturimetria domiciliare non e raccomandata di routine nel lattante con "
    "bronchiolite lieve gestito a domicilio."
)
SECONDARY_QUOTE = (
    "Il documento conferma l'offerta attiva della vaccinazione antinfluenzale a "
    "partire dai sei mesi di vita per la stagione in corso."
)


def _item(*, tag: TaxonomyTag, score: float, summary: str, quote: str) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key=f"src-{tag.value}",
            name=f"Fonte {tag.value}",
            source_type="rss",
            country="IT",
            reliability_tier=4,
        ),
        content=ContentBlock(
            title="Titolo",
            canonical_url=f"https://esempio.it/{tag.value}",
            published_at=IN_WEEK,
            document_type=DocumentType.GUIDELINE,
            key_passages=[KeyPassage(quote=quote)],
        ),
        classification=Classification(geo=Geo.IT, taxonomy_tags=[tag]),
        scoring=ScoringBlock(
            score_total=score,
            subscores=Subscores(
                pls_relevance=5,
                clinical_impact=4,
                operational_impact=4,
                source_trust=5,
                novelty=4,
                actionability=4,
                urgency=5 if tag is TaxonomyTag.DRUG_SAFETY else 2,
            ),
        ),
        editorial=EditorialBlock(
            headline_operational=f"Titolo conclusivo {tag.value}",
            why_it_matters="In pratica, questo significa rivedere un passaggio della gestione.",
            what_to_do=["Ricontrolla i due aspetti indicati"],
            summary=summary,
            confidence=Confidence.HIGH,
        ),
    )


def _issue() -> tuple[str, str]:
    items = [
        _item(
            tag=TaxonomyTag.DRUG_SAFETY,
            score=95,
            summary=PRIORITY_SUMMARY,
            quote=PRIORITY_QUOTE,
        ),
        _item(
            tag=TaxonomyTag.VACCINATIONS,
            score=70,
            summary=SECONDARY_SUMMARY,
            quote=SECONDARY_QUOTE,
        ),
    ]
    newsletter = compose_newsletter(items, WEEK)
    assert len(newsletter.slots) == 2, "fixture must produce a priority and a secondary"
    return render_html(newsletter), render_plain_text(newsletter)


def test_priority_item_is_fully_developed() -> None:
    html, text = _issue()

    assert PRIORITY_SUMMARY in html
    assert PRIORITY_QUOTE in html
    assert PRIORITY_SUMMARY in text


def test_secondary_items_stay_compact() -> None:
    """A secondary update gets the title, the consequence and one action - no more."""
    html, text = _issue()

    assert SECONDARY_SUMMARY not in html
    assert SECONDARY_QUOTE not in html
    assert SECONDARY_SUMMARY not in text


def test_every_item_keeps_title_consequence_and_action() -> None:
    html, _ = _issue()

    assert "Titolo conclusivo drug_safety" in html
    assert "Titolo conclusivo vaccinations" in html
    assert html.count("Ricontrolla i due aspetti indicati") == 2
    assert "Cosa fare ora" in html
