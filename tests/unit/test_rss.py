"""Tests for RSS connector - S007."""
from __future__ import annotations

import pytest

from oykos.ingestion.rss import fetch_rss, _parse_date, _detect_language
from oykos.models.source import FetchConfig, Source
from oykos.models.taxonomy import SourceType, Tier


def _make_rss_source() -> Source:
    return Source(
        key="test_rss",
        name="Test RSS",
        url="https://example.com/feed",
        source_type=SourceType.RSS,
        tier=Tier.TIER_1_ITALY,
        reliability=4,
        country="IT",
        fetch_config=FetchConfig(max_items=5),
    )


@pytest.mark.asyncio
async def test_fetch_rss_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test RSS parsing with a mock feed."""
    import feedparser

    mock_feed_xml = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <item>
          <title>Test Article 1</title>
          <link>https://example.com/article-1</link>
          <description>Summary of article 1</description>
        </item>
        <item>
          <title>Test Article 2</title>
          <link>https://example.com/article-2</link>
          <description>Summary of article 2</description>
        </item>
      </channel>
    </rss>"""

    original_parse = feedparser.parse
    def mock_parse(url_or_text: str):
        return original_parse(mock_feed_xml)

    monkeypatch.setattr(feedparser, "parse", mock_parse)

    source = _make_rss_source()
    items = await fetch_rss(source)
    assert len(items) == 2
    assert items[0].content.title == "Test Article 1"
    assert items[0].source.key == "test_rss"
    assert items[0].source.reliability_tier == 4


@pytest.mark.asyncio
async def test_fetch_rss_empty_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    import feedparser

    empty_xml = """<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>"""
    original_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _: original_parse(empty_xml))

    items = await fetch_rss(_make_rss_source())
    assert items == []


@pytest.mark.asyncio
async def test_fetch_rss_skips_items_without_link(monkeypatch: pytest.MonkeyPatch) -> None:
    import feedparser

    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><title>No Link</title></item>
      <item><title>Has Link</title><link>https://example.com/ok</link></item>
    </channel></rss>"""
    original_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _: original_parse(xml))

    items = await fetch_rss(_make_rss_source())
    assert len(items) == 1
    assert items[0].content.title == "Has Link"


def test_detect_language_italian() -> None:
    source = _make_rss_source()
    assert _detect_language(source) == "it"


def test_detect_language_foreign() -> None:
    source = _make_rss_source()
    source.country = "US"
    assert _detect_language(source) == "en"
