"""End-to-end: fixtures in, reviewed newsletter out.

Walks the whole blueprint workflow against realistic Italian source material with
only the LLM and SMTP boundaries stubbed:

    ingest -> gate -> score -> rank -> compose -> review -> deliver

The assertions are about editorial outcomes, not implementation details: noise is
excluded, the hard rules hold, the review gate blocks delivery until an editor
signs off, and a delivered issue never repeats.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.config import Settings
from oykos.db.repository import NewsItemRepository, NewsletterRepository
from oykos.db.subscribers import SubscriberRepository
from oykos.db.tables import Base
from oykos.models.news_item import (
    Citation,
    Classification,
    ContentBlock,
    EditorialBlock,
    KeyPassage,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    ExclusionReason,
    Geo,
    IssueStatus,
    Section,
    TaxonomyTag,
)
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.template import render_html
from oykos.pipeline import weekly
from oykos.processing.gates import evaluate_gates
from oykos.processing.scoring import detect_penalties, score_item

FIXTURES = Path(__file__).parent.parent / "fixtures" / "news_items.json"
WEEK = "2026-W17"
# Items only ship in the week they were published, so fixtures carry that date.
IN_WEEK = datetime.fromisocalendar(2026, 17, 3).replace(tzinfo=UTC)

# Subscores an editor would assign, keyed by fixture. Kept in the test rather
# than the fixture file so the fixtures stay pure source material.
SUBSCORES: dict[str, dict[str, int]] = {
    "aifa_safety_communication": {
        "pls_relevance": 5, "clinical_impact": 5, "operational_impact": 4,
        "source_trust": 5, "novelty": 4, "actionability": 5, "urgency": 5,
    },
    "respivirnet_surveillance": {
        "pls_relevance": 5, "clinical_impact": 4, "operational_impact": 4,
        "source_trust": 5, "novelty": 3, "actionability": 4, "urgency": 5,
    },
    "sisac_acn_update": {
        "pls_relevance": 4, "clinical_impact": 1, "operational_impact": 5,
        "source_trust": 5, "novelty": 4, "actionability": 4, "urgency": 3,
    },
    "poct_rapid_test": {
        "pls_relevance": 4, "clinical_impact": 3, "operational_impact": 4,
        "source_trust": 5, "novelty": 3, "actionability": 4, "urgency": 2,
    },
    "ecdc_threat_report": {
        "pls_relevance": 4, "clinical_impact": 4, "operational_impact": 3,
        "source_trust": 5, "novelty": 3, "actionability": 4, "urgency": 4,
    },
    "vendor_marketing_noise": {
        "pls_relevance": 1, "clinical_impact": 0, "operational_impact": 0,
        "source_trust": 0, "novelty": 1, "actionability": 0, "urgency": 0,
    },
    "generalist_filler": {
        "pls_relevance": 2, "clinical_impact": 0, "operational_impact": 0,
        "source_trust": 2, "novelty": 1, "actionability": 0, "urgency": 0,
    },
}


def _load_fixtures() -> dict[str, dict[str, Any]]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def _build_item(key: str, raw: dict[str, Any]) -> NewsItem:
    """Turn fixture source material into a classified, scored NewsItem."""
    item = NewsItem(
        source=SourceRef(
            key=raw["source_key"],
            name=raw["source_name"],
            source_type="scrape",
            country=raw["country"],
            reliability_tier=raw["reliability_tier"],
        ),
        content=ContentBlock(
            title=raw["title"],
            canonical_url=raw["canonical_url"],
            published_at=IN_WEEK,
            raw_text=raw["raw_text"],
            document_type=DocumentType(raw["document_type"]),
            key_passages=[KeyPassage(quote=q) for q in raw["key_passages"]],
        ),
        classification=Classification(
            geo=Geo(raw["geo"]),
            taxonomy_tags=[TaxonomyTag(t) for t in raw["taxonomy_tags"]],
            device_related=raw.get("device_related", False),
            tests_mentioned=raw.get("tests_mentioned", []),
        ),
        scoring=ScoringBlock(subscores=Subscores(**SUBSCORES[key])),
    )

    # Editorial output, as the synthesis step would have produced it.
    if raw["key_passages"]:
        item.editorial = EditorialBlock(
            headline_operational=raw["title"][:90],
            why_it_matters="Cambia una decisione operativa in ambulatorio.",
            what_to_do=["Verificare in studio", "Informare i genitori"],
            summary=raw["raw_text"][:400],
            confidence=Confidence.HIGH,
            citations=[Citation(
                claim_id="c1",
                source_url=raw["canonical_url"],
                supporting_passage_ref="P1",
            )],
        )

    item.scoring.penalties = detect_penalties(item, [])
    item.scoring = score_item(item)
    item.gating = evaluate_gates(item)
    return item


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        openai_api_key="sk-test",
        smtp_username="sender@example.it",
        smtp_password="pw",
        base_url="https://oykos.example.it",
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def items() -> dict[str, NewsItem]:
    return {key: _build_item(key, raw) for key, raw in _load_fixtures().items()}


# ── Gating ────────────────────────────────────────────────

def test_institutional_sources_clear_the_gates(items) -> None:
    for key in (
        "aifa_safety_communication",
        "respivirnet_surveillance",
        "sisac_acn_update",
        "poct_rapid_test",
        "ecdc_threat_report",
    ):
        assert items[key].gating.passed, f"{key} should be publishable"


def test_vendor_marketing_is_excluded(items) -> None:
    gating = items["vendor_marketing_noise"].gating
    assert not gating.passed
    assert ExclusionReason.VENDOR_MARKETING in gating.exclusions


def test_generalist_filler_is_excluded(items) -> None:
    gating = items["generalist_filler"].gating
    assert not gating.passed
    assert ExclusionReason.GENERALIST_NEWS in gating.exclusions


# ── Composition ───────────────────────────────────────────

def test_composed_issue_contains_only_publishable_items(items, settings) -> None:
    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    published = {str(slot.item_id) for slot in newsletter.slots}

    assert str(items["vendor_marketing_noise"].item_id) not in published
    assert str(items["generalist_filler"].item_id) not in published
    assert newsletter.slots


def test_safety_communication_leads_the_issue(items, settings) -> None:
    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    assert newsletter.slots[0].section is Section.TOP_PRIORITY


def test_issue_carries_the_header_furniture(items, settings) -> None:
    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    assert newsletter.tldr
    assert 6 <= newsletter.reading_time_minutes <= 8


def test_rendered_issue_has_every_blueprint_block(items, settings) -> None:
    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    html = render_html(
        newsletter,
        settings.newsletter_title,
        unsubscribe_url="https://oykos.example.it/unsubscribe/tok",
        preferences_url="https://oykos.example.it/preferences/tok",
    )

    assert "Che cosa merita attenzione questa settimana" in html
    # v2.0 labels the implication by what the source justifies.
    assert "Merita attenzione" in html
    assert "Fonti" in html
    assert "Annulla iscrizione" in html
    assert "Informazione professionale destinata a medici" in html


def test_top_items_are_flagged_for_human_review(items, settings) -> None:
    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    assert newsletter.slots[0].editorial.review.needs_human_review


# ── Delivery ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_run_holds_for_review_then_delivers(
    session, settings, items, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict] = []

    async def fake_send(**kwargs) -> bool:
        sent.append(kwargs)
        return True

    async def fake_bulk(settings, messages) -> int:
        sent.extend(
            {
                "to_emails": [m.to_email],
                "subject": m.subject,
                "list_unsubscribe_url": m.list_unsubscribe_url,
            }
            for m in messages
        )
        return len(messages)

    monkeypatch.setattr(weekly, "send_newsletter", fake_send)
    monkeypatch.setattr(weekly, "send_bulk", fake_bulk)

    item_repo = NewsItemRepository(session)
    for item in items.values():
        await item_repo.save(item)

    subscribers = SubscriberRepository(session)
    row = await subscribers.create(email="pls@example.it")
    await subscribers.confirm(row.confirm_token)
    await session.commit()

    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    newsletter.subject_line = "Briefing settimanale"
    newsletter_repo = NewsletterRepository(session)
    await newsletter_repo.save(newsletter)
    await session.commit()

    # Nothing is approved yet, so the delivery run must not ship it.
    assert await weekly.send_approved_issues(session, settings) == []
    assert sent == []

    # An editor approves the issue.
    await newsletter_repo.mark_approved(str(newsletter.issue_id), "medical_editor")
    await session.commit()

    delivered = await weekly.send_approved_issues(session, settings)

    assert [n.week for n in delivered] == [WEEK]
    assert sent, "an approved issue must reach the subscriber"
    assert sent[0]["to_emails"] == ["pls@example.it"]
    assert "unsubscribe" in sent[0]["list_unsubscribe_url"]

    stored = await newsletter_repo.get_by_week(WEEK)
    assert stored is not None
    assert stored.status is IssueStatus.SENT


@pytest.mark.asyncio
async def test_sent_items_never_come_back(
    session, settings, items, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_send(**kwargs) -> bool:
        return True

    async def fake_bulk(settings, messages) -> int:
        return len(messages)

    monkeypatch.setattr(weekly, "send_newsletter", fake_send)
    monkeypatch.setattr(weekly, "send_bulk", fake_bulk)

    item_repo = NewsItemRepository(session)
    for item in items.values():
        await item_repo.save(item)

    subscribers = SubscriberRepository(session)
    row = await subscribers.create(email="pls@example.it")
    await subscribers.confirm(row.confirm_token)
    await session.commit()

    newsletter = compose_newsletter(
        list(items.values()), WEEK, settings.newsletter_title,
    )
    newsletter_repo = NewsletterRepository(session)
    await newsletter_repo.save(newsletter)
    await newsletter_repo.mark_approved(str(newsletter.issue_id), "medical_editor")
    await session.commit()

    await weekly.send_approved_issues(session, settings)

    remaining = {
        item.item_id
        for item in await item_repo.get_unsent_candidates(min_score=0.0, limit=50)
    }
    assert not remaining & {slot.item_id for slot in newsletter.slots}
