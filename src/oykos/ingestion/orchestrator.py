"""Daily ingestion orchestrator - S010."""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.repository import NewsItemRepository
from oykos.ingestion.dedup import is_duplicate
from oykos.ingestion.normalizer import clean_html, normalize_url
from oykos.ingestion.rss import fetch_rss
from oykos.models.news_item import NewsItem
from oykos.models.source import Source, get_source_registry
from oykos.models.taxonomy import SourceType

logger = logging.getLogger(__name__)


async def ingest_source(source: Source, session: AsyncSession) -> list[NewsItem]:
    """Ingest articles from a single source, dedup, persist."""
    if not source.enabled:
        return []

    raw_items: list[NewsItem] = []
    if source.source_type == SourceType.RSS:
        raw_items = await fetch_rss(source)
    else:
        # Scrape/API/PDF connectors - stub for now, returns empty
        logger.info("Skipping non-RSS source: %s (%s)", source.name, source.source_type.value)
        return []

    repo = NewsItemRepository(session)
    saved: list[NewsItem] = []

    for item in raw_items:
        # Normalize
        item.content.canonical_url = normalize_url(item.content.canonical_url)
        if item.content.raw_text:
            item.content.raw_text = clean_html(item.content.raw_text)

        # Dedup
        if await is_duplicate(item, session):
            continue

        # Set geo from source
        from oykos.models.taxonomy import Geo, Tier
        if source.tier == Tier.TIER_1_ITALY:
            item.classification.geo = Geo.IT
        elif source.tier == Tier.TIER_2_EUROPE:
            item.classification.geo = Geo.EU
        else:
            item.classification.geo = Geo.GLOBAL

        # Persist
        try:
            await repo.save(item)
            saved.append(item)
        except Exception:
            logger.exception("Failed to save item: %s", item.content.canonical_url)

    await session.commit()
    logger.info("Ingested %d new items from %s", len(saved), source.name)
    return saved


async def run_daily_ingestion(session: AsyncSession) -> list[NewsItem]:
    """Run ingestion across all enabled sources."""
    registry = get_source_registry()
    all_saved: list[NewsItem] = []

    for source in registry.values():
        items = await ingest_source(source, session)
        all_saved.extend(items)

    logger.info("Daily ingestion complete: %d total new items", len(all_saved))
    return all_saved
