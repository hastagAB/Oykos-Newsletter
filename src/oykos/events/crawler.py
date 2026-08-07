"""Event crawler - registry to candidate events.

Politeness is deliberate: sources are grouped by domain, requests to the same
host are serialised with a delay, and a resolved listing URL is cached so
discovery is not repeated every week.

Programme PDFs are followed because target professions, ECM credits and
registration deadlines are usually stated there rather than on the listing page.
Without them the audience filter would be guessing at exactly the fields the
hard data quality rule forbids inventing.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from oykos.events.discovery import discover_listing_url
from oykos.events.extractor import extract_events
from oykos.events.models import Event
from oykos.events.registry import EventSource
from oykos.ingestion.scraper import fetch_html
from oykos.llm.client import LLMClient

logger = logging.getLogger(__name__)

PER_HOST_DELAY_SECONDS = 1.5
MAX_HOST_CONCURRENCY = 4
MAX_PAGE_TEXT_CHARS = 14000
PDF_MAX_CHARS = 8000


@dataclass
class CrawlHealth:
    """What the run did, so an empty section can be explained rather than guessed."""

    scheduled: int = 0
    fetched: int = 0
    failed: list[str] = field(default_factory=list)
    discovered: dict[str, str] = field(default_factory=dict)
    events_extracted: int = 0
    sources_without_events: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"scheduled={self.scheduled} fetched={self.fetched} "
            f"failed={len(self.failed)} discovered={len(self.discovered)} "
            f"events={self.events_extracted}"
        )


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    try:
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(" ", strip=True)[:MAX_PAGE_TEXT_CHARS]
    finally:
        soup.decompose()


def find_programme_pdf(html: str, base_url: str) -> str:
    """First PDF link that looks like a programme or brochure."""
    from urllib.parse import urljoin  # noqa: PLC0415

    soup = BeautifulSoup(html, "html.parser")
    markers = ("programma", "brochure", "locandina", "programme", "depliant")
    try:
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href", ""))
            if ".pdf" not in href.lower():
                continue
            haystack = f"{href} {anchor.get_text(' ', strip=True)}".lower()
            if any(marker in haystack for marker in markers):
                return urljoin(base_url, href)
    finally:
        soup.decompose()
    return ""


async def read_pdf_text(client: httpx.AsyncClient, url: str) -> str:
    """Extract text from a programme PDF, or empty when it cannot be read."""
    try:
        from io import BytesIO  # noqa: PLC0415

        from pypdf import PdfReader  # noqa: PLC0415

        resp = await client.get(url, timeout=45.0, follow_redirects=True)
        resp.raise_for_status()
        reader = PdfReader(BytesIO(resp.content))
        text = " ".join((page.extract_text() or "") for page in reader.pages[:10])
        return " ".join(text.split())[:PDF_MAX_CHARS]
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not read programme PDF %s: %s", url, exc)
        return ""


async def crawl_source(
    source: EventSource,
    client: httpx.AsyncClient,
    llm: LLMClient,
    health: CrawlHealth,
    resolved: dict[str, str],
) -> list[Event]:
    """Crawl one registry row and return the events found on it."""
    listing_url = resolved.get(source.source_id, "")

    if not listing_url:
        for candidate in source.start_urls:
            if not source.needs_discovery:
                listing_url = candidate
                break
            listing_url = await discover_listing_url(client, candidate, source.domain)
            if listing_url:
                health.discovered[source.source_id] = listing_url
                break

    if not listing_url:
        health.failed.append(f"{source.source_id} ({source.domain}): no listing found")
        return []

    try:
        html = await fetch_html(client, listing_url)
    except Exception as exc:  # noqa: BLE001
        health.failed.append(f"{source.source_id}: {type(exc).__name__}")
        return []

    if not html:
        health.failed.append(f"{source.source_id}: empty response")
        return []

    health.fetched += 1
    text = page_text(html)

    programme_url = find_programme_pdf(html, listing_url)
    if programme_url:
        pdf_text = await read_pdf_text(client, programme_url)
        if pdf_text:
            text = f"{text}\n\n[PROGRAMME PDF {programme_url}]\n{pdf_text}"

    events = await extract_events(text, listing_url, source.source_id, source.name, llm)
    for event in events:
        if programme_url and not event.programme_url:
            event.programme_url = programme_url
        event.last_seen_at = datetime.now(UTC)

    if not events:
        health.sources_without_events.append(source.source_id)
    health.events_extracted += len(events)
    return events


async def crawl_sources(
    sources: list[EventSource],
    llm: LLMClient,
    client: httpx.AsyncClient | None = None,
    resolved: dict[str, str] | None = None,
) -> tuple[list[Event], CrawlHealth]:
    """Crawl the scheduled registry rows, one request at a time per host."""
    health = CrawlHealth(scheduled=len(sources))
    resolved = resolved or {}

    by_host: dict[str, list[EventSource]] = {}
    for source in sources:
        by_host.setdefault(source.domain.lower(), []).append(source)

    owns_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True)
    semaphore = asyncio.Semaphore(MAX_HOST_CONCURRENCY)
    collected: list[Event] = []

    async def run_host(host_sources: list[EventSource]) -> list[Event]:
        found: list[Event] = []
        async with semaphore:
            for source in host_sources:
                found.extend(await crawl_source(source, client, llm, health, resolved))
                await asyncio.sleep(PER_HOST_DELAY_SECONDS)
        return found

    try:
        results = await asyncio.gather(
            *(run_host(group) for group in by_host.values()),
            return_exceptions=True,
        )
    finally:
        if owns_client:
            await client.aclose()

    for result in results:
        if isinstance(result, BaseException):
            health.failed.append(f"host task: {type(result).__name__}")
            continue
        collected.extend(result)

    logger.info("Event crawl: %s", health.summary())
    for failure in health.failed:
        logger.warning("Event source failed: %s", failure)
    return collected, health
