"""RSS/Atom connector - S007."""
from __future__ import annotations

import logging
from datetime import datetime

import feedparser
import httpx

from oykos.models.news_item import ContentBlock, NewsItem, SourceRef
from oykos.models.source import Source

logger = logging.getLogger(__name__)


async def fetch_rss(source: Source, client: httpx.AsyncClient | None = None) -> list[NewsItem]:
    """Fetch and parse an RSS/Atom feed, returning NewsItems."""
    items: list[NewsItem] = []
    try:
        if client:
            resp = await client.get(source.url, timeout=source.fetch_config.timeout_seconds)
            feed = feedparser.parse(resp.text)
        else:
            feed = feedparser.parse(source.url)

        max_items = source.fetch_config.max_items
        for entry in feed.entries[:max_items]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            if not link or not title:
                continue

            published_at = _parse_date(entry)
            summary = entry.get("summary", "")

            item = NewsItem(
                source=SourceRef(
                    key=source.key,
                    name=source.name,
                    source_type=source.source_type.value,
                    country=source.country,
                    reliability_tier=source.reliability,
                ),
                content=ContentBlock(
                    title=title,
                    canonical_url=link,
                    published_at=published_at,
                    language=_detect_language(source),
                    raw_text=summary,
                ),
            )
            items.append(item)
    except Exception:
        logger.exception("Error fetching RSS from %s", source.name)

    return items


def _parse_date(entry: dict) -> datetime | None:
    """Parse published date from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed))
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _detect_language(source: Source) -> str:
    """Infer language from source country."""
    return "it" if source.country == "IT" else "en"
