"""Tests for dedup engine - S009."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.db.tables import Base
from oykos.db.repository import NewsItemRepository
from oykos.ingestion.dedup import is_duplicate, title_similarity
from oykos.models.news_item import ContentBlock, NewsItem, SourceRef


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_item(url: str = "https://example.com/1", title: str = "Test Article") -> NewsItem:
    return NewsItem(
        source=SourceRef(key="test", name="Test", source_type="rss", country="IT", reliability_tier=4),
        content=ContentBlock(title=title, canonical_url=url),
    )


@pytest.mark.asyncio
async def test_not_duplicate_fresh(session: AsyncSession) -> None:
    item = _make_item()
    assert not await is_duplicate(item, session)


@pytest.mark.asyncio
async def test_duplicate_by_url(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item()
    await repo.save(item)
    await session.commit()

    dup = _make_item(url="https://example.com/1", title="Different Title")
    assert await is_duplicate(dup, session)


@pytest.mark.asyncio
async def test_duplicate_by_title_similarity(session: AsyncSession) -> None:
    repo = NewsItemRepository(session)
    item = _make_item(url="https://example.com/1", title="AIFA pubblica avviso sicurezza paracetamolo")
    await repo.save(item)
    await session.commit()

    dup = _make_item(url="https://example.com/2", title="AIFA pubblica avviso sicurezza paracetamolo pediatrico")
    assert await is_duplicate(dup, session)


def test_title_similarity_identical() -> None:
    assert title_similarity("hello world", "hello world") == 1.0


def test_title_similarity_different() -> None:
    assert title_similarity("hello world", "completely different") < 0.5


def test_title_similarity_close() -> None:
    s = title_similarity("AIFA safety alert on drug X", "AIFA safety alert on drug X updated")
    assert s > 0.8
