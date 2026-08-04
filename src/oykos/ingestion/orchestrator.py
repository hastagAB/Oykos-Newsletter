"""Daily ingestion orchestrator - S010.

Runs Monday to Friday. Fetches every enabled source with the connector that
matches its type, normalises, de-duplicates, records noise penalties and
persists. It never sends anything: composition and delivery are weekly.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.repository import NewsItemRepository
from oykos.ingestion.dedup import is_duplicate
from oykos.ingestion.normalizer import clean_html, normalize_url
from oykos.ingestion.rss import fetch_rss
from oykos.ingestion.scraper import USER_AGENT, fetch_scrape
from oykos.models.news_item import NewsItem
from oykos.models.source import Source, get_source_registry
from oykos.models.taxonomy import Geo, SourceType, Tier
from oykos.processing.scoring import detect_penalties

logger = logging.getLogger(__name__)

# This is a weekly briefing on what changed, not an archive. Anything older than
# this is dropped before it costs an LLM call. Items whose date cannot be
# determined are kept: many institutional pages publish none.
MAX_ITEM_AGE_DAYS = 90

TIER_GEO: dict[Tier, Geo] = {
    Tier.TIER_1_ITALY: Geo.IT,
    Tier.TIER_2_EUROPE: Geo.EU,
    Tier.TIER_3_GLOBAL: Geo.GLOBAL,
    Tier.RADAR: Geo.IT,
}


async def fetch_source(
    source: Source,
    client: httpx.AsyncClient | None = None,
) -> list[NewsItem]:
    """Dispatch to the connector that matches the source type."""
    if source.source_type is SourceType.RSS:
        return await fetch_rss(source, client)
    if source.source_type is SourceType.SCRAPE:
        return await fetch_scrape(source, client)
    logger.info(
        "No connector for %s source %s - skipping",
        source.source_type.value,
        source.name,
    )
    return []


async def ingest_source(
    source: Source,
    session: AsyncSession,
    client: httpx.AsyncClient | None = None,
) -> list[NewsItem]:
    """Ingest articles from a single source: fetch, normalise, dedup, persist."""
    if not source.enabled:
        return []

    raw_items = await fetch_source(source, client)
    if not raw_items:
        return []

    repo = NewsItemRepository(session)
    recent_titles = await repo.get_recent_titles(days=28)
    saved: list[NewsItem] = []
    cutoff = datetime.now(UTC) - timedelta(days=MAX_ITEM_AGE_DAYS)
    stale = 0

    for item in raw_items:
        published = item.content.published_at
        if published is not None and published < cutoff:
            stale += 1
            continue

        item.content.canonical_url = normalize_url(item.content.canonical_url)
        if item.content.raw_text:
            item.content.raw_text = clean_html(item.content.raw_text)

        if await is_duplicate(item, session):
            continue

        item.classification.geo = TIER_GEO[source.tier]
        item.scoring.penalties = detect_penalties(item, recent_titles)

        try:
            await repo.save(item)
        except Exception:
            logger.exception("Failed to save item: %s", item.content.canonical_url)
            continue

        saved.append(item)
        recent_titles.append(item.content.title)

    await session.commit()
    if stale:
        logger.info("Skipped %d stale item(s) from %s", stale, source.name)
    logger.info("Ingested %d new items from %s", len(saved), source.name)
    return saved


async def run_daily_ingestion(session: AsyncSession) -> list[NewsItem]:
    """Run ingestion across all enabled sources in the registry."""
    registry = get_source_registry()
    all_saved: list[NewsItem] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for source in registry.values():
            try:
                all_saved.extend(await ingest_source(source, session, client))
            except Exception:
                logger.exception("Ingestion failed for source %s", source.name)

    logger.info("Daily ingestion complete: %d total new items", len(all_saved))
    return all_saved
