"""Deduplication - canonical URL match, then title similarity.

Items at or above the similarity threshold are dropped. The band just below it
earns the duplicate penalty instead (see oykos.processing.scoring).
"""
from __future__ import annotations

import logging
from difflib import SequenceMatcher

from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.repository import NewsItemRepository
from oykos.ingestion.normalizer import normalize_url
from oykos.models.news_item import NewsItem

logger = logging.getLogger(__name__)

TITLE_SIMILARITY_THRESHOLD = 0.85
RECENT_WINDOW_DAYS = 28


def title_similarity(a: str, b: str) -> float:
    """Compute similarity ratio between two titles."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


async def is_duplicate(item: NewsItem, session: AsyncSession) -> bool:
    """Check if item is a duplicate via URL match or title similarity."""
    repo = NewsItemRepository(session)

    canonical = normalize_url(item.content.canonical_url)
    if await repo.url_exists(canonical):
        logger.debug("Duplicate URL: %s", canonical)
        return True

    title = item.content.title.lower().strip()
    for existing in await repo.get_recent_titles(days=RECENT_WINDOW_DAYS):
        ratio = SequenceMatcher(None, title, existing.lower().strip()).ratio()
        if ratio >= TITLE_SIMILARITY_THRESHOLD:
            logger.debug("Duplicate title (%.2f): %s", ratio, item.content.title)
            return True

    return False
