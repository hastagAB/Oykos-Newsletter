"""Tests for editorial guidelines v2.0.

The central change: "nuova evidenza, quindi il pediatra deve fare qualcosa" is
wrong. An item may legitimately conclude that nothing changes, and the system
must be able to carry that conclusion all the way to the reader instead of
dropping the item or inventing an action for it.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    Newsletter,
    NewsletterSlot,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    ImplicationKind,
    Section,
    TaxonomyTag,
)
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.template import (
    IMPLICATION_LABELS,
    NO_CHANGE_NOTES,
    render_html,
    render_plain_text,
)

WEEK = "2026-W32"
IN_WEEK = "2026-08-05T09:00:00Z"


def _slot(kind: ImplicationKind, actions: list[str] | None = None) -> NewsletterSlot:
    return NewsletterSlot(
        position=1,
        section=Section.CLINICAL,
        item_id=uuid4(),
        headline="Titolo",
        source_name="SIP",
        source_url="https://sip.it/a",
        editorial=EditorialBlock(
            headline_operational="Ex very preterm: frequenti alterazioni spirometriche",
            why_it_matters="Lo studio osservazionale descrive un'associazione.",
            implication_kind=kind,
            what_to_do=actions or [],
            summary="Dettaglio.",
            confidence=Confidence.MEDIUM,
        ),
    )


def _newsletter(slot: NewsletterSlot) -> Newsletter:
    return Newsletter(week=WEEK, subject_line="Oggetto", slots=[slot])


# ── An item with no action must survive composition ───────

def _item_without_action() -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key="frontiers", name="Frontiers", source_type="rss",
            country="EU", reliability_tier=4,
        ),
        content=ContentBlock(
            title="Studio osservazionale",
            canonical_url="https://esempio.it/studio",
            published_at=IN_WEEK,  # type: ignore[arg-type]
            raw_text="Testo.",
            document_type=DocumentType.STUDY,
        ),
        classification=Classification(taxonomy_tags=[TaxonomyTag.RESPIRATORY]),
        scoring=ScoringBlock(
            score_total=70.0,
            subscores=Subscores(
                pls_relevance=4, actionability=3, clinical_impact=4,
                operational_impact=3, source_trust=4,
            ),
        ),
        editorial=EditorialBlock(
            headline_operational="Ex very preterm: frequenti alterazioni spirometriche",
            why_it_matters="Associazione descritta in eta' prescolare.",
            implication_kind=ImplicationKind.NO_CHANGE,
            what_to_do=[],
            summary="Dettaglio clinico.",
            confidence=Confidence.MEDIUM,
        ),
    )


def test_item_without_an_action_is_still_published() -> None:
    """Requiring what_to_do would silently delete the honest conclusions."""
    newsletter = compose_newsletter([_item_without_action()], WEEK)

    assert len(newsletter.slots) == 1


def test_item_without_a_headline_is_dropped() -> None:
    """A headline is still required: there is nothing to render without one."""
    item = _item_without_action()
    item.editorial.headline_operational = ""

    assert compose_newsletter([item], WEEK).slots == []


# ── The label reflects the conclusion ─────────────────────

@pytest.mark.parametrize(
    ("kind", "label"),
    [
        (ImplicationKind.CHANGES_PRACTICE, "Indicazione della fonte"),
        (ImplicationKind.WORTH_ATTENTION, "Merita attenzione"),
        (ImplicationKind.MAY_CONSIDER, "Può essere utile considerare"),
    ],
)
def test_action_label_matches_the_kind(kind: ImplicationKind, label: str) -> None:
    html = render_html(_newsletter(_slot(kind, ["Ricontrolla l'anamnesi"])))

    assert label in html
    assert "Cosa fare ora" not in html


def test_no_change_states_that_nothing_changes() -> None:
    html = render_html(_newsletter(_slot(ImplicationKind.NO_CHANGE)))

    assert NO_CHANGE_NOTES["no_change"] in html
    assert "Cosa fare ora" not in html


def test_insufficient_evidence_says_so() -> None:
    html = render_html(_newsletter(_slot(ImplicationKind.INSUFFICIENT)))

    assert NO_CHANGE_NOTES["insufficient"] in html


def test_no_change_reaches_the_plain_text_part_too() -> None:
    text = render_plain_text(_newsletter(_slot(ImplicationKind.NO_CHANGE)))

    assert NO_CHANGE_NOTES["no_change"] in text
    assert "Cosa fare ora" not in text


def test_action_label_reaches_the_plain_text_part() -> None:
    text = render_plain_text(
        _newsletter(_slot(ImplicationKind.CHANGES_PRACTICE, ["AIFA indica di non utilizzare"])),
    )

    assert "Indicazione della fonte" in text
    assert "AIFA indica di non utilizzare" in text


def test_no_change_kinds_have_no_action_label() -> None:
    """A conclusion of 'nothing changes' has no action to label."""
    assert "no_change" not in IMPLICATION_LABELS
    assert "insufficient" not in IMPLICATION_LABELS
