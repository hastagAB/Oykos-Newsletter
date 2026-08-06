"""Tests for the daily and weekly pipeline orchestration.

These exercise the real ordering guarantees of the blueprint workflow with the
LLM and SMTP boundaries stubbed out.
"""
from __future__ import annotations

from datetime import UTC, datetime

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
from oykos.models.taxonomy import Confidence, DocumentType, Geo, IssueStatus, TaxonomyTag
from oykos.pipeline import daily, weekly


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
        recipient_emails="pls@example.it",
        base_url="https://oykos.example.it",
        _env_file=None,
    )  # type: ignore[call-arg]


def _candidate(index: int, tags: list[TaxonomyTag], *, geo: Geo = Geo.IT) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key="sip",
            name="SIP",
            source_type="rss",
            country="IT" if geo is Geo.IT else "EU",
            reliability_tier=4,
        ),
        content=ContentBlock(
            title=f"Articolo {index}",
            canonical_url=f"https://sip.it/{index}",
            published_at=datetime.now(UTC),
            raw_text="Testo integrale del documento.",
            document_type=DocumentType.GUIDELINE,
            key_passages=[KeyPassage(quote="Testo integrale del documento.")],
        ),
        classification=Classification(geo=geo, taxonomy_tags=tags),
        scoring=ScoringBlock(
            score_total=max(0.0, 90.0 - index),
            subscores=Subscores(
                pls_relevance=4,
                actionability=4,
                clinical_impact=4,
                operational_impact=3,
                source_trust=4,
                urgency=5 if TaxonomyTag.DRUG_SAFETY in tags else 2,
            ),
        ),
        editorial=EditorialBlock(
            headline_operational=f"Titolo operativo {index}",
            why_it_matters=f"Motivo numero {index}.",
            what_to_do=["Verificare", "Informare"],
            summary="Dettaglio clinico e operativo.",
            confidence=Confidence.HIGH,
            citations=[Citation(claim_id="c1", source_url="https://www.aifa.gov.it/x")],
        ),
    )


async def _seed(session: AsyncSession, count: int = 14) -> list[NewsItem]:
    repo = NewsItemRepository(session)
    tag_cycle = [
        [TaxonomyTag.DRUG_SAFETY],
        [TaxonomyTag.RESPIRATORY],
        [TaxonomyTag.ACN_AGREEMENTS],
        [TaxonomyTag.RAPID_TESTS],
        [TaxonomyTag.CME_TRAINING],
    ]
    items = []
    for i in range(count):
        item = _candidate(i, tag_cycle[i % len(tag_cycle)], geo=Geo.IT if i % 3 else Geo.EU)
        await repo.save(item)
        items.append(item)
    await session.commit()
    return items


@pytest.fixture(autouse=True)
def _stub_boundaries(monkeypatch: pytest.MonkeyPatch) -> dict:
    state: dict = {"sent": []}

    async def fake_send(**kwargs) -> bool:
        state["sent"].append(kwargs)
        return True

    async def fake_bulk(settings, messages) -> int:
        state["sent"].extend(
            {
                "to_emails": [m.to_email],
                "subject": m.subject,
                "list_unsubscribe_url": m.list_unsubscribe_url,
            }
            for m in messages
        )
        return len(messages)

    async def fake_subjects(newsletter, client):
        return "Oggetto A", "Preheader", "Oggetto B"

    async def fake_passages(item, client):
        return item

    async def fake_synth(item, client):
        return item.editorial

    async def fake_verify(editorial, item, client):
        return editorial

    monkeypatch.setattr(weekly, "send_newsletter", fake_send)
    monkeypatch.setattr(weekly, "send_bulk", fake_bulk)
    monkeypatch.setattr(weekly, "generate_subject_line", fake_subjects)
    monkeypatch.setattr(weekly, "attach_key_passages", fake_passages)
    monkeypatch.setattr(weekly, "synthesize_editorial", fake_synth)
    monkeypatch.setattr(weekly, "verify_claims", fake_verify)
    return state


@pytest.mark.asyncio
async def test_gather_candidates_returns_fresh_items(session) -> None:
    await _seed(session)
    candidates = await weekly.gather_candidates(NewsItemRepository(session))
    assert len(candidates) >= 10


@pytest.mark.asyncio
async def test_weekly_pipeline_holds_issue_for_review(session, settings) -> None:
    await _seed(session)

    newsletter = await weekly.run_weekly_pipeline(session, settings)

    assert newsletter is not None
    # Top-3 items always require sign-off, so the issue must be held.
    assert newsletter.status is IssueStatus.IN_REVIEW
    assert await NewsletterRepository(session).get_by_week(newsletter.week) is not None


@pytest.mark.asyncio
async def test_weekly_pipeline_sends_when_review_is_satisfied(
    session, settings, _stub_boundaries, monkeypatch,
) -> None:
    await _seed(session)
    monkeypatch.setattr(
        weekly, "compose_newsletter",
        _compose_pre_approved(weekly.compose_newsletter),
    )

    newsletter = await weekly.run_weekly_pipeline(session, settings)

    assert newsletter is not None
    assert newsletter.status is IssueStatus.SENT
    assert _stub_boundaries["sent"]


def _compose_pre_approved(original):
    def wrapper(*args, **kwargs):
        newsletter = original(*args, **kwargs)
        for slot in newsletter.slots:
            slot.editorial.review.review_status = "approved"
        return newsletter

    return wrapper


@pytest.mark.asyncio
async def test_weekly_pipeline_marks_items_sent(
    session, settings, _stub_boundaries, monkeypatch,
) -> None:
    await _seed(session)
    monkeypatch.setattr(
        weekly, "compose_newsletter",
        _compose_pre_approved(weekly.compose_newsletter),
    )

    newsletter = await weekly.run_weekly_pipeline(session, settings)
    assert newsletter is not None

    repo = NewsItemRepository(session)
    remaining = await repo.get_unsent_candidates(min_score=0.0, limit=50)
    sent_ids = {slot.item_id for slot in newsletter.slots}
    assert not sent_ids & {item.item_id for item in remaining}


@pytest.mark.asyncio
async def test_weekly_pipeline_returns_none_without_candidates(session, settings) -> None:
    assert await weekly.run_weekly_pipeline(session, settings) is None


@pytest.mark.asyncio
async def test_preview_mode_never_sends(session, settings, _stub_boundaries, monkeypatch) -> None:
    await _seed(session)
    monkeypatch.setattr(
        weekly, "compose_newsletter",
        _compose_pre_approved(weekly.compose_newsletter),
    )
    preview_settings = settings.model_copy(update={"preview_mode": True})

    newsletter = await weekly.run_weekly_pipeline(session, preview_settings)

    assert newsletter is not None
    assert newsletter.status is IssueStatus.IN_REVIEW
    assert _stub_boundaries["sent"] == []


@pytest.mark.asyncio
async def test_deliver_prefers_confirmed_subscribers(session, settings, _stub_boundaries) -> None:
    subscriber_repo = SubscriberRepository(session)
    row = await subscriber_repo.create(email="doc@example.it")
    await subscriber_repo.confirm(row.confirm_token)
    await session.commit()

    await _seed(session)
    newsletter = weekly.compose_newsletter(
        await weekly.gather_candidates(NewsItemRepository(session)),
        "2026-W17",
    )
    newsletter.subject_line = "A"

    assert await weekly.deliver(newsletter, settings, session)
    assert _stub_boundaries["sent"][0]["to_emails"] == ["doc@example.it"]
    assert "unsubscribe" in _stub_boundaries["sent"][0]["list_unsubscribe_url"]


@pytest.mark.asyncio
async def test_deliver_falls_back_to_configured_recipients(
    session, settings, _stub_boundaries,
) -> None:
    await _seed(session)
    newsletter = weekly.compose_newsletter(
        await weekly.gather_candidates(NewsItemRepository(session)),
        "2026-W17",
    )
    newsletter.subject_line = "A"

    assert await weekly.deliver(newsletter, settings, session)
    assert _stub_boundaries["sent"][0]["to_emails"] == ["pls@example.it"]


@pytest.mark.asyncio
async def test_daily_pipeline_classifies_scores_and_gates(
    session, settings, monkeypatch,
) -> None:
    repo = NewsItemRepository(session)
    raw = _candidate(99, [TaxonomyTag.RESPIRATORY])
    raw.scoring = ScoringBlock()
    raw.editorial = EditorialBlock()
    await repo.save(raw)
    await session.commit()

    async def fake_ingest(_session, _settings=None):
        return []

    async def fake_classify(item, client):
        return (
            Classification(geo=Geo.IT, taxonomy_tags=[TaxonomyTag.RESPIRATORY]),
            Subscores(
                pls_relevance=4,
                actionability=4,
                clinical_impact=4,
                operational_impact=3,
                source_trust=4,
                urgency=2,
            ),
        )

    async def fake_alerts(items, s, sess):
        return []

    monkeypatch.setattr(daily, "run_daily_ingestion", fake_ingest)
    monkeypatch.setattr(daily, "classify_item", fake_classify)
    monkeypatch.setattr(daily, "process_alerts", fake_alerts)

    processed = await daily.run_daily_pipeline(session, settings)

    assert len(processed) == 1
    assert processed[0].scoring.score_total > 0
    assert processed[0].gating.passed


@pytest.mark.asyncio
async def test_daily_pipeline_skips_items_that_fail_classification(
    session, settings, monkeypatch,
) -> None:
    repo = NewsItemRepository(session)
    raw = _candidate(98, [TaxonomyTag.RESPIRATORY])
    raw.scoring = ScoringBlock()
    await repo.save(raw)
    await session.commit()

    async def fake_ingest(_session, _settings=None):
        return []

    async def failing_classify(item, client):
        raise RuntimeError("model down")

    async def fake_alerts(items, s, sess):
        return []

    monkeypatch.setattr(daily, "run_daily_ingestion", fake_ingest)
    monkeypatch.setattr(daily, "classify_item", failing_classify)
    monkeypatch.setattr(daily, "process_alerts", fake_alerts)

    assert await daily.run_daily_pipeline(session, settings) == []


@pytest.mark.asyncio
async def test_daily_pipeline_aborts_when_the_llm_is_systematically_failing(
    session, settings, monkeypatch,
) -> None:
    """An outage or an empty billing account must not look like a quiet news week."""
    repo = NewsItemRepository(session)
    for offset in range(daily.MAX_CONSECUTIVE_FAILURES + 2):
        raw = _candidate(200 + offset, [TaxonomyTag.RESPIRATORY])
        raw.scoring = ScoringBlock()
        await repo.save(raw)
    await session.commit()

    attempts = 0

    async def fake_ingest(_session, _settings=None):
        return []

    async def failing_classify(item, client):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("credit_balance_exhausted")

    async def fake_alerts(items, s, sess):
        return []

    monkeypatch.setattr(daily, "run_daily_ingestion", fake_ingest)
    monkeypatch.setattr(daily, "classify_item", failing_classify)
    monkeypatch.setattr(daily, "process_alerts", fake_alerts)

    with pytest.raises(daily.ClassificationUnavailableError):
        await daily.run_daily_pipeline(session, settings)

    assert attempts == daily.MAX_CONSECUTIVE_FAILURES
