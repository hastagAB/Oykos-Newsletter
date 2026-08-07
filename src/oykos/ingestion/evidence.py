"""Europe PMC connector - international pediatric evidence.

The editorial feedback of 2026-08-07 asks the bot to compete Italian and
international sources on relevance to PLS practice rather than on geography.
The AAP, JAMA and PubMed feeds all block automated clients, so the peer-reviewed
literature reaches us through Europe PMC, which indexes the same journals and
serves a documented REST API.

Queries are journal-restricted and date-restricted. What comes back is a
candidate, not a selection: it is classified and scored like everything else.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from oykos.models.news_item import ContentBlock, NewsItem, SourceRef
from oykos.models.source import Source

logger = logging.getLogger(__name__)

EUROPE_PMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# The journals the editorial feedback names, plus the primary care titles a PLS
# would actually be handed by a colleague.
JOURNALS: tuple[str, ...] = (
    "Pediatrics",
    "JAMA pediatrics",
    "The Lancet. Child & adolescent health",
    "Archives of disease in childhood",
    "The Journal of pediatrics",
    "Acta paediatrica",
    "European journal of pediatrics",
    "BMJ (Clinical research ed.)",
    "Annals of family medicine",
)

LOOKBACK_DAYS = 21
ABSTRACT_MAX_CHARS = 4000


def _build_query(lookback_days: int, today: date | None = None) -> str:
    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=lookback_days)
    journals = " OR ".join(f'JOURNAL:"{name}"' for name in JOURNALS)
    return (
        f"({journals}) AND (FIRST_PDATE:[{start.isoformat()} TO {end.isoformat()}])"
        " AND (SRC:MED)"
    )


async def fetch_europe_pmc(
    source: Source,
    client: httpx.AsyncClient | None = None,
) -> list[NewsItem]:
    """Fetch recent articles from the named journals as NewsItem candidates."""
    params = {
        "query": _build_query(LOOKBACK_DAYS),
        "format": "json",
        "pageSize": str(source.fetch_config.max_items),
        "resultType": "core",
        "sort": "P_PDATE_D desc",
    }
    owns_client = client is None
    client = client or httpx.AsyncClient()
    try:
        resp = await client.get(
            EUROPE_PMC_SEARCH,
            params=params,
            timeout=source.fetch_config.timeout_seconds,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        logger.exception("Error querying Europe PMC for %s", source.name)
        return []
    finally:
        if owns_client:
            await client.aclose()

    results = payload.get("resultList", {}).get("result", [])
    items = [_to_news_item(source, record) for record in results]
    kept = [item for item in items if item is not None]
    logger.info("Europe PMC returned %d records, %d usable", len(results), len(kept))
    return kept


def _to_news_item(source: Source, record: dict[str, Any]) -> NewsItem | None:
    title = (record.get("title") or "").strip().rstrip(".")
    url = _canonical_url(record)
    if not title or not url:
        return None

    # An abstract is what makes an article judgeable. Without one there is
    # nothing to score beyond a headline, and a headline is not evidence.
    abstract = (record.get("abstractText") or "").strip()
    if not abstract:
        return None

    return NewsItem(
        source=SourceRef(
            key=source.key,
            name=_journal_name(record) or source.name,
            source_type=source.source_type.value,
            country=source.country,
            reliability_tier=source.reliability,
        ),
        content=ContentBlock(
            title=title,
            canonical_url=url,
            published_at=_parse_date(record.get("firstPublicationDate")),
            language="en",
            raw_text=abstract[:ABSTRACT_MAX_CHARS],
        ),
    )


def _canonical_url(record: dict[str, Any]) -> str:
    doi = record.get("doi")
    if doi:
        return f"https://doi.org/{doi}"
    pmid = record.get("pmid")
    if pmid:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return ""


def _journal_name(record: dict[str, Any]) -> str:
    journal = record.get("journalInfo", {}).get("journal", {})
    return (journal.get("title") or "").strip()


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=UTC)
    except ValueError:
        return None
