"""Controlled HTML scraper connector - S007b.

Most of the Italian institutional core feed (Ministry, AIFA, ISS, SISAC, Garante
Privacy, Agenas) and the EU regulators (ECDC, EMA) publish no usable RSS. Without
this connector the entire Tier-1 whitelist of the blueprint is unreachable.

Scraping is deliberately "controlled": a declared user agent, an explicit
allow-list of sources, bounded concurrency, per-source selectors and a hard cap
on the number of pages fetched per run.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import NamedTuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from oykos.ingestion.normalizer import clean_html, normalize_url
from oykos.models.news_item import ContentBlock, NewsItem, SourceRef
from oykos.models.source import Source

logger = logging.getLogger(__name__)

USER_AGENT = "OykosNewsletterBot/1.0 (+https://oykos.example/bot; pediatric news aggregation)"
MAX_DETAIL_CONCURRENCY = 4
MAX_ARTICLE_CHARS = 20000
MIN_LINK_TEXT_CHARS = 15

# A source once linked a 150 MB video from its listing page; parsing it as HTML
# took 2.8 GB and the OOM killer ended the run. Never hold an unbounded remote
# response in memory, and never hand non-HTML bytes to the parser.
MAX_DOWNLOAD_BYTES = 3_000_000
_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "")

# Most CMSs put the publication date in the permalink. Without this a 2016
# archive page looks exactly as fresh as today's news.
_URL_DATE = re.compile(r"/(20[0-2]\d)/(\d{1,2})(?:/(\d{1,2}))?/")
_JSONLD_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"', re.I)
_META_DATE = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?:article:published_time|og:published_time|"""
    r"""datePublished|pubdate|sailthru\.date|parsely-pub-date|date|"""
    r"""DC\.date\.issued|DC\.Date|dcterms\.created)["'][^>]+content=["']([^"']+)["']""",
    re.I,
)
_TIME_TAG = re.compile(r"""<time[^>]+datetime=["']([^"']+)["']""", re.I)

# Half our Italian sources print the date only in prose.
_IT_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
    "dicembre": 12,
}
_IT_TEXT_DATE = re.compile(
    rf"\b(\d{{1,2}})\s+({'|'.join(_IT_MONTHS)})\s+(20\d{{2}})\b",
    re.I,
)
_IT_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d{2})\b")

# Sanity bound for anything parsed out of free text.
EARLIEST_PLAUSIBLE_YEAR = 2000

# Phrases that mean the reader cannot actually read what we would link them to.
_PAYWALL_MARKERS = (
    "riservato esclusivamente ai soci",
    "riservato ai soci",
    "area riservata",
    "effettua il login",
    "accedi per continuare",
    "contenuto riservato",
    "abbonati per",
    "subscribe to continue",
    "members only",
)


def is_paywalled(text: str) -> bool:
    """True when the extracted body is a login wall rather than an article."""
    lowered = text.lower()
    return any(marker in lowered for marker in _PAYWALL_MARKERS)


def _as_utc(raw: str) -> datetime | None:
    """Parse an ISO-ish timestamp, tolerating the variants publishers emit."""
    cleaned = raw.strip().replace("Z", "+00:00")
    for candidate in (cleaned, cleaned[:19], cleaned[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _plausible(moment: datetime | None) -> datetime | None:
    """Reject dates that cannot be a publication date for this issue."""
    if moment is None:
        return None
    now = datetime.now(UTC)
    if moment > now + timedelta(days=1) or moment.year < EARLIEST_PLAUSIBLE_YEAR:
        return None
    return moment


def extract_published_at(html: str, url: str) -> datetime | None:
    """Best-effort publication date, most trustworthy signal first.

    Half our sources put no ISO date in the markup but do print one in Italian
    prose, so the cascade ends with text formats. Those are the least reliable,
    hence last and bounded by a plausibility check.
    """
    match = _URL_DATE.search(url)
    if match:
        year, month, day = match.group(1), match.group(2), match.group(3) or "1"
        try:
            found = _plausible(datetime(int(year), int(month), int(day), tzinfo=UTC))
        except ValueError:
            found = None
        if found:
            return found

    for pattern in (_JSONLD_DATE, _META_DATE, _TIME_TAG):
        for raw in pattern.findall(html):
            found = _plausible(_as_utc(raw))
            if found:
                return found

    text_match = _IT_TEXT_DATE.search(html)
    if text_match:
        day, month_name, year = text_match.groups()
        month = _IT_MONTHS[month_name.lower()]
        try:
            found = _plausible(datetime(int(year), month, int(day), tzinfo=UTC))
        except ValueError:
            found = None
        if found:
            return found

    numeric_match = _IT_NUMERIC_DATE.search(html)
    if numeric_match:
        # Italian convention is day first.
        day, month, year = numeric_match.groups()
        try:
            found = _plausible(datetime(int(year), int(month), int(day), tzinfo=UTC))
        except ValueError:
            found = None
        if found:
            return found

    return None


# Paths that are navigation rather than content.
_SKIP_URL_MARKERS = (
    "javascript:",
    "mailto:",
    "#",
    "/login",
    "/cerca",
    "/search",
    "/privacy-policy",
    "/cookie",
    "/feed",
    "/wp-content/uploads/",
    ".css",
    ".js",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".zip",
    ".gz",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
)

_CONTENT_SELECTORS = (
    "main",
    "article",
    "[role=main]",
    "#content",
    ".content",
    ".entry-content",
    ".article-body",
)


def _is_useful_link(href: str, text: str, base_url: str, must_contain: str) -> bool:
    if not href or not text or len(text.strip()) < MIN_LINK_TEXT_CHARS:
        return False
    lowered = href.lower()
    if any(marker in lowered for marker in _SKIP_URL_MARKERS):
        return False
    absolute = urljoin(base_url, href)
    if urlparse(absolute).netloc != urlparse(base_url).netloc:
        return False
    return not must_contain or must_contain.lower() in absolute.lower()


def extract_links(html: str, source: Source) -> list[tuple[str, str]]:
    """Return (absolute_url, link_text) pairs from a source's listing page."""
    soup = BeautifulSoup(html, "html.parser")
    try:
        scope: Tag | BeautifulSoup = soup

        selector = source.fetch_config.link_selector
        if selector:
            anchors = soup.select(selector)
        else:
            for candidate in _CONTENT_SELECTORS:
                found = soup.select_one(candidate)
                if found is not None:
                    scope = found
                    break
            anchors = scope.find_all("a", href=True)

        seen: set[str] = set()
        links: list[tuple[str, str]] = []
        for anchor in anchors:
            href = str(anchor.get("href") or "")
            text = anchor.get_text(strip=True)
            if not _is_useful_link(href, text, source.url, source.fetch_config.url_must_contain):
                continue
            absolute = normalize_url(urljoin(source.url, href))
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append((absolute, text))

        return links
    finally:
        # A soup is a cyclic parent/child graph, so refcounting never frees it.
        # Across a full ingestion that is hundreds of trees waiting on the GC.
        soup.decompose()


def extract_article_text(html: str, source: Source) -> str:
    """Pull the readable body text out of an article page."""
    soup = BeautifulSoup(html, "html.parser")
    try:
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        selector = source.fetch_config.content_selector
        node: Tag | BeautifulSoup | None = None
        if selector:
            node = soup.select_one(selector)
        if node is None:
            for candidate in _CONTENT_SELECTORS:
                node = soup.select_one(candidate)
                if node is not None:
                    break
        if node is None:
            node = soup.body or soup

        return clean_html(str(node))[:MAX_ARTICLE_CHARS]
    finally:
        soup.decompose()


async def fetch_html(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a URL as HTML, refusing anything oversized or not markup.

    Returns an empty string rather than raising: a single bad link must not end
    the run.
    """
    async with client.stream("GET", url) as response:
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type not in _HTML_CONTENT_TYPES:
            logger.info("Skipping %s: content-type %s", url, content_type or "unknown")
            return ""

        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_DOWNLOAD_BYTES:
            logger.info("Skipping %s: declared %s bytes", url, declared)
            return ""

        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                logger.warning("Aborting %s: exceeded %d bytes", url, MAX_DOWNLOAD_BYTES)
                return ""
            chunks.append(chunk)

        body = b"".join(chunks)

    encoding = response.encoding or "utf-8"
    return body.decode(encoding, errors="replace")


class _Detail(NamedTuple):
    text: str
    published_at: datetime | None
    access_limited: bool


async def _fetch_detail(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    source: Source,
    url: str,
) -> _Detail:
    async with semaphore:
        try:
            html = await fetch_html(client, url)
        except httpx.HTTPError:
            logger.warning("Detail fetch failed for %s", url)
            return _Detail("", None, False)
        if not html:
            return _Detail("", None, False)

        text = extract_article_text(html, source)
        walled = is_paywalled(text)
        if walled:
            logger.info("Members-only, will be reported as a document notice: %s", url)
        return _Detail(text, extract_published_at(html, url), walled)


async def fetch_scrape(source: Source, client: httpx.AsyncClient | None = None) -> list[NewsItem]:
    """Fetch a listing page, follow its article links and build NewsItems."""
    owns_client = client is None
    timeout = httpx.Timeout(source.fetch_config.timeout_seconds)
    headers = {"User-Agent": USER_AGENT, **source.fetch_config.custom_headers}
    http = client or httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
    )

    try:
        try:
            listing_html = await fetch_html(http, source.url)
        except httpx.HTTPError:
            logger.warning("Listing fetch failed for %s (%s)", source.name, source.url)
            return []
        if not listing_html:
            return []

        links = extract_links(listing_html, source)[: source.fetch_config.max_items]
        if not links:
            logger.info("No article links found for %s", source.name)
            return []

        semaphore = asyncio.Semaphore(MAX_DETAIL_CONCURRENCY)
        details = await asyncio.gather(
            *(_fetch_detail(http, semaphore, source, url) for url, _ in links),
        )

        source_ref = SourceRef(
            key=source.key,
            name=source.name,
            source_type=source.source_type.value,
            country=source.country,
            reliability_tier=source.reliability,
        )

        return [
            NewsItem(
                ingested_at=datetime.now(UTC),
                source=source_ref,
                content=ContentBlock(
                    title=title,
                    canonical_url=url,
                    published_at=detail.published_at,
                    language="it" if source.country == "IT" else "en",
                    raw_text=detail.text,
                    access_limited=detail.access_limited,
                ),
            )
            for (url, title), detail in zip(links, details, strict=True)
            if detail.text
        ]
    finally:
        if owns_client:
            await http.aclose()
