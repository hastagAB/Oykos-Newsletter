"""Content normalizer - S008."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urldefrag

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    """Canonical URL: strip fragment and trailing slash."""
    return urldefrag(url).url.rstrip("/")


def clean_html(raw: str) -> str:
    """Strip HTML tags, collapse whitespace."""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def text_hash(text: str) -> str:
    """SHA-256 hash of normalized text for dedup."""
    normalized = text.lower().strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def truncate(text: str, max_length: int = 5000) -> str:
    """Truncate text to max length, preserving word boundaries."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.8:
        return truncated[:last_space] + "..."
    return truncated + "..."
