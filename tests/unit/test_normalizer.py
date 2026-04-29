"""Tests for normalizer - S008."""
from __future__ import annotations

from oykos.ingestion.normalizer import clean_html, normalize_url, text_hash, truncate


def test_normalize_url_strips_fragment() -> None:
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_normalize_url_strips_trailing_slash() -> None:
    assert normalize_url("https://example.com/page/") == "https://example.com/page"


def test_clean_html_strips_tags() -> None:
    result = clean_html("<p>Hello <b>world</b></p>")
    assert result == "Hello world"


def test_clean_html_collapses_whitespace() -> None:
    result = clean_html("Hello    world   test")
    assert result == "Hello world test"


def test_text_hash_deterministic() -> None:
    h1 = text_hash("test article title")
    h2 = text_hash("test article title")
    assert h1 == h2


def test_text_hash_case_insensitive() -> None:
    h1 = text_hash("Test Article Title")
    h2 = text_hash("test article title")
    assert h1 == h2


def test_truncate_short_text() -> None:
    assert truncate("short text", 100) == "short text"


def test_truncate_long_text() -> None:
    long_text = "word " * 2000
    result = truncate(long_text, 100)
    assert len(result) <= 104  # 100 + "..."
    assert result.endswith("...")
