"""Tests for ingestion orchestrator - S010."""
from __future__ import annotations

import pytest
import pytest_asyncio
import feedparser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.db.tables import Base
from oykos.db.repository import NewsItemRepository
from oykos.ingestion.orchestrator import ingest_source
from oykos.models.source import FetchConfig, Source
from oykos.models.taxonomy import Geo, SourceType, Tier


MOCK_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>AIFA ritira lotto paracetamolo pediatrico</title><link>https://example.com/a</link><description>Desc A</description></item>
  <item><title>Nuove linee guida bronchiolite SIP 2026</title><link>https://example.com/b</link><description>Desc B</description></item>
  <item><title>Vaccinazione anti-RSV raccomandata da EMA</title><link>https://example.com/c</link><description>Desc C</description></item>
</channel></rss>"""


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _make_source(key: str = "test_src", tier: Tier = Tier.TIER_1_ITALY) -> Source:
    return Source(
        key=key,
        name="Test Source",
        url="https://example.com/feed",
        source_type=SourceType.RSS,
        tier=tier,
        reliability=4,
        country="IT" if tier == Tier.TIER_1_ITALY else "EU",
        fetch_config=FetchConfig(max_items=10),
    )


@pytest.mark.asyncio
async def test_ingest_source_rss(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    original_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _: original_parse(MOCK_FEED))

    source = _make_source()
    items = await ingest_source(source, session)
    assert len(items) == 3
    assert all(i.classification.geo == Geo.IT for i in items)


@pytest.mark.asyncio
async def test_ingest_dedup_on_second_run(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    original_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _: original_parse(MOCK_FEED))

    source = _make_source()
    first_run = await ingest_source(source, session)
    assert len(first_run) == 3

    second_run = await ingest_source(source, session)
    assert len(second_run) == 0


@pytest.mark.asyncio
async def test_ingest_disabled_source(session: AsyncSession) -> None:
    source = _make_source()
    source.enabled = False
    items = await ingest_source(source, session)
    assert items == []


@pytest.mark.asyncio
async def test_ingest_sets_geo_for_european(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    original_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _: original_parse(MOCK_FEED))

    source = _make_source(tier=Tier.TIER_2_EUROPE)
    items = await ingest_source(source, session)
    assert all(i.classification.geo == Geo.EU for i in items)
