"""Tests for database repository - S005."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.db.repository import NewsItemRepository, NewsletterRepository
from oykos.db.tables import Base
from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    Newsletter,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    Geo,
    IssueStatus,
    Setting,
    TaxonomyTag,
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_item(url: str = "https://example.com/article-1") -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key="aifa_safety",
            name="AIFA",
            source_type="scrape",
            country="IT",
            reliability_tier=5,
        ),
        content=ContentBlock(
            title="Test AIFA Safety Alert",
            canonical_url=url,
            published_at=datetime(2026, 4, 1, tzinfo=UTC),
            document_type=DocumentType.SAFETY_COMMUNICATION,
        ),
        classification=Classification(
            geo=Geo.IT,
            taxonomy_tags=[TaxonomyTag.DRUG_SAFETY],
            setting=Setting.TERRITORY,
            pls_relevance=0.9,
        ),
    )


@pytest.mark.asyncio
async def test_save_and_retrieve(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    retrieved = await repo.get_by_id(str(item.item_id))
    assert retrieved is not None
    assert retrieved.content.title == "Test AIFA Safety Alert"
    assert retrieved.source.key == "aifa_safety"
    assert retrieved.classification.geo == Geo.IT


@pytest.mark.asyncio
async def test_url_exists(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    assert await repo.url_exists("https://example.com/article-1")
    assert not await repo.url_exists("https://example.com/nonexistent")


@pytest.mark.asyncio
async def test_get_by_url(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    found = await repo.get_by_url("https://example.com/article-1")
    assert found is not None
    assert str(found.item_id) == str(item.item_id)


@pytest.mark.asyncio
async def test_update_scoring(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    new_scoring = ScoringBlock(
        score_total=85.0,
        subscores=Subscores(pls_relevance=5, clinical_impact=4, source_trust=5),
    )
    await repo.update_scoring(str(item.item_id), new_scoring)
    await session.commit()

    updated = await repo.get_by_id(str(item.item_id))
    assert updated is not None
    assert updated.scoring.score_total == 85.0


@pytest.mark.asyncio
async def test_update_editorial(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    new_ed = EditorialBlock(
        headline_operational="AIFA: Nuovo avviso su farmaco pediatrico",
        why_it_matters="Impatto diretto sulla prescrizione in studio",
        what_to_do=["Verificare scorte", "Informare genitori"],
        summary="L'AIFA ha emesso una comunicazione...",
        confidence=Confidence.HIGH,
    )
    await repo.update_editorial(str(item.item_id), new_ed)
    await session.commit()

    updated = await repo.get_by_id(str(item.item_id))
    assert updated is not None
    assert updated.editorial.headline_operational == "AIFA: Nuovo avviso su farmaco pediatrico"
    assert updated.editorial.confidence == Confidence.HIGH


@pytest.mark.asyncio
async def test_get_candidates(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    for i in range(5):
        item = _make_item(url=f"https://example.com/article-{i}")
        item.scoring.score_total = float(i * 20)
        await repo.save(item)
    await session.commit()

    # Update scores directly
    candidates = await repo.get_candidates(min_score=40.0)
    assert len(candidates) >= 2


@pytest.mark.asyncio
async def test_get_recent_titles(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    titles = await repo.get_recent_titles(days=7)
    assert "Test AIFA Safety Alert" in titles


@pytest.mark.asyncio
async def test_newsletter_save_and_retrieve(session: AsyncSession) -> None:
    repo = NewsletterRepository(session)
    nl = Newsletter(week="2026-W17", subject_line="PLS Briefing - W17")
    await repo.save(nl)
    await session.commit()

    retrieved = await repo.get_by_week("2026-W17")
    assert retrieved is not None
    assert retrieved.subject_line == "PLS Briefing - W17"
    assert retrieved.status == IssueStatus.DRAFT


@pytest.mark.asyncio
async def test_newsletter_update_status(session: AsyncSession) -> None:
    repo = NewsletterRepository(session)
    nl = Newsletter(week="2026-W18")
    await repo.save(nl)
    await session.commit()

    await repo.update_status(str(nl.issue_id), IssueStatus.SENT)
    await session.commit()

    updated = await repo.get_by_week("2026-W18")
    assert updated is not None
    assert updated.status == IssueStatus.SENT
