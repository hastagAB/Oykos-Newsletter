"""Event page discovery.

Two thirds of the registry rows point at a homepage. Before anything can be
extracted, the crawler has to find the page that actually lists dated events.
Resolved URLs are persisted with the date they were verified, so discovery is
paid for once rather than on every run.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from oykos.ingestion.scraper import fetch_html

logger = logging.getLogger(__name__)

# The words an Italian society uses for its events page.
LISTING_WORDS = (
    "eventi",
    "congressi",
    "congresso",
    "corsi",
    "formazione",
    "ecm",
    "appuntamenti",
    "agenda",
    "calendario",
    "convegni",
    "manifestazioni",
    # Several Italian society and PCO sites label the section in English.
    "congress",
    "calendar",
    "events",
)

SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")
MAX_SITEMAP_URLS = 3000
MAX_CANDIDATES = 10

# An archive of past editions has MORE dates than the upcoming calendar, so it
# wins a naive date count. Observed on fimp.pro, which resolved to
# /eventi/eventi-passati. These pages are refused outright.
ARCHIVE_WORDS = (
    "passat",
    "archivio",
    "archive",
    "precedenti",
    "storico",
    "edizioni-",
    "scadut",
)

# A page that announces itself as upcoming is preferred over a generic one.
UPCOMING_WORDS = ("prossim", "calendario", "agenda", "in-programma", "futuri")
UPCOMING_BONUS = 1.5

# Tried when link and sitemap inspection find nothing, which happens when the
# navigation is rendered client side. Several Italian society sites answer 200
# to any path, so a candidate still has to prove itself on the date count.
CONVENTIONAL_PATHS = (
    "/eventi",
    "/eventi/",
    "/congressi",
    "/formazione",
    "/corsi",
    "/appuntamenti",
    "/agenda",
    "/calendario",
)

# A listing page shows several dates. One date is an article about an event.
MIN_DATES_FOR_LISTING = 2

_DATE_PATTERNS = (
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(
        r"\b\d{1,2}\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|"
        r"agosto|settembre|ottobre|novembre|dicembre)\b",
        re.IGNORECASE,
    ),
)


def count_dates(text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in _DATE_PATTERNS)


def _same_domain(url: str, domain: str) -> bool:
    host = urlparse(url).netloc.lower()
    return domain.lower().replace("www.", "") in host.replace("www.", "")


def is_archive_url(url: str, text: str = "") -> bool:
    haystack = f"{urlparse(url).path.lower()} {text.lower()}"
    return any(word in haystack for word in ARCHIVE_WORDS)


def _looks_like_listing(url: str, text: str = "") -> bool:
    if is_archive_url(url, text):
        return False
    haystack = f"{urlparse(url).path.lower()} {text.lower()}"
    return any(word in haystack for word in LISTING_WORDS)


def candidates_from_html(html: str, base_url: str, domain: str) -> list[str]:
    """Internal links whose path or anchor text suggests an events page."""
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    try:
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", ""))
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            absolute = urljoin(base_url, href)
            if not absolute.startswith("http") or not _same_domain(absolute, domain):
                continue
            if _looks_like_listing(absolute, anchor.get_text(" ", strip=True)):
                found.append(absolute.split("#")[0])
    finally:
        soup.decompose()
    return list(dict.fromkeys(found))


def candidates_from_sitemap(sitemap_xml: str, domain: str) -> list[str]:
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap_xml)[:MAX_SITEMAP_URLS]
    return list(
        dict.fromkeys(
            url for url in urls if _same_domain(url, domain) and _looks_like_listing(url)
        ),
    )


async def discover_listing_url(
    client: httpx.AsyncClient,
    start_url: str,
    domain: str,
) -> str:
    """Return the best event listing URL for a site, or empty if none is found.

    A candidate wins by containing several dates: that is what separates a
    calendar from a news article that happens to mention an event.
    """
    try:
        home = await fetch_html(client, start_url)
    except Exception:
        logger.warning("Discovery could not open %s", start_url)
        home = ""

    candidates: list[str] = []
    if home:
        candidates.extend(candidates_from_html(home, start_url, domain))

    if len(candidates) < MAX_CANDIDATES:
        root = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
        for path in SITEMAP_PATHS:
            try:
                sitemap = await fetch_html(client, f"{root}{path}")
            except Exception as exc:  # noqa: BLE001
                logger.debug("No sitemap at %s%s: %s", root, path, exc)
                continue
            if sitemap:
                candidates.extend(candidates_from_sitemap(sitemap, domain))
                break

    if not candidates:
        root = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
        candidates.extend(f"{root}{path}" for path in CONVENTIONAL_PATHS)

    # Some societies list their events on the front page. It is judged on dates
    # like any other candidate, so this cannot smuggle in a news homepage.
    candidates.append(start_url)

    best_url = ""
    best_rank = 0.0
    for url in list(dict.fromkeys(candidates))[:MAX_CANDIDATES]:
        try:
            html = await fetch_html(client, url)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Candidate %s unreachable: %s", url, exc)
            continue
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        try:
            dates = count_dates(soup.get_text(" ", strip=True))
        finally:
            soup.decompose()
        if dates < MIN_DATES_FOR_LISTING:
            continue
        rank = float(dates)
        if any(word in urlparse(url).path.lower() for word in UPCOMING_WORDS):
            rank *= UPCOMING_BONUS
        if rank > best_rank:
            best_url, best_rank = url, rank

    if not best_url:
        logger.info("No event listing found for %s", domain)
        return ""

    logger.info("Discovered listing for %s: %s (rank %.1f)", domain, best_url, best_rank)
    return best_url
