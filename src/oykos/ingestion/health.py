"""Check every source in the registry actually returns items.

Feed URLs rot and scraper selectors drift. This fetches each enabled source and
reports what came back, so a broken source is found before it silently starves
an issue rather than after.

Run with ``oykos check-sources``.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx

from oykos.ingestion.orchestrator import fetch_source
from oykos.ingestion.scraper import USER_AGENT
from oykos.models.source import get_source_registry
from oykos.models.taxonomy import SourceType

logger = logging.getLogger(__name__)

CONCURRENCY = 5
TIMEOUT_SECONDS = 45.0


@dataclass(frozen=True)
class SourceCheck:
    key: str
    name: str
    source_type: SourceType
    items: int
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.items > 0 and not self.error


async def _check_one(
    source_key: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> SourceCheck:
    source = get_source_registry()[source_key]
    async with semaphore:
        try:
            items = await fetch_source(source, client)
        except Exception as exc:  # noqa: BLE001 - the whole point is to report it
            return SourceCheck(source.key, source.name, source.source_type, 0, str(exc)[:120])
    return SourceCheck(source.key, source.name, source.source_type, len(items))


async def check_sources() -> list[SourceCheck]:
    """Fetch every enabled source once and report how many items it yielded."""
    registry = get_source_registry()
    enabled = [key for key, source in registry.items() if source.enabled]
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *(_check_one(key, client, semaphore) for key in enabled),
        )

    return sorted(results, key=lambda r: (r.ok, r.key))
