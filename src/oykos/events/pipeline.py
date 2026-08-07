"""Event persistence and the weekly event pipeline.

Selection never consults ``first_seen_at`` or ``last_seen_at``. Those exist for
monitoring and change detection only: an event that has appeared in a previous
issue may appear again while it is still upcoming and still ranks.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.config import Settings
from oykos.db.tables import EventRow, ResolvedEventSourceRow
from oykos.events.crawler import CrawlHealth, crawl_sources
from oykos.events.models import Event, EventFormat, PLSFit
from oykos.events.registry import get_event_sources, select_for_run
from oykos.events.selection import select_events
from oykos.llm.client import LLMClient

logger = logging.getLogger(__name__)

MAX_DISCOVERY_FAILURES = 3


def _naive(moment: date | datetime | None) -> datetime | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        return moment.replace(tzinfo=None) if moment.tzinfo else moment
    return datetime(moment.year, moment.month, moment.day)  # noqa: DTZ001 - DB stores naive UTC


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolved_urls(self) -> dict[str, str]:
        rows = (await self.session.execute(select(ResolvedEventSourceRow))).scalars().all()
        return {r.source_id: r.listing_url for r in rows if r.listing_url}

    async def remember_listing(self, source_id: str, listing_url: str) -> None:
        row = await self.session.get(ResolvedEventSourceRow, source_id)
        if row is None:
            row = ResolvedEventSourceRow(source_id=source_id)
            self.session.add(row)
        row.listing_url = listing_url
        row.verified_at = datetime.now(UTC).replace(tzinfo=None)
        row.failure_count = 0
        row.needs_manual_review = False
        await self.session.flush()

    async def record_failure(self, source_id: str) -> None:
        row = await self.session.get(ResolvedEventSourceRow, source_id)
        if row is None:
            row = ResolvedEventSourceRow(source_id=source_id)
            self.session.add(row)
        row.failure_count += 1
        row.needs_manual_review = row.failure_count >= MAX_DISCOVERY_FAILURES
        await self.session.flush()

    async def upsert(self, event: Event) -> None:
        key = "|".join(event.dedup_key)
        existing = (
            await self.session.execute(
                select(EventRow).where(EventRow.dedup_key == key),
            )
        ).scalars().first()

        now = datetime.now(UTC).replace(tzinfo=None)
        if existing is not None:
            existing.last_seen_at = now
            existing.relevance_score = event.relevance_score
            existing.pls_fit = event.pls_fit.value
            if event.why_relevant:
                existing.why_relevant = event.why_relevant
            existing.source_urls = list(
                dict.fromkeys([*existing.source_urls, *event.source_urls]),
            )
            await self.session.flush()
            return

        self.session.add(
            EventRow(
                event_id=str(event.event_id),
                source_id=event.source_id,
                title=event.title,
                promoter=event.promoter,
                organiser=event.organiser,
                detail_url=event.detail_url,
                programme_url=event.programme_url,
                source_urls=event.source_urls,
                start_date=_naive(event.start_date) or now,
                end_date=_naive(event.end_date),
                city=event.city,
                region=event.region,
                venue=event.venue,
                event_format=event.event_format.value,
                stated_audience=event.stated_audience,
                programme_evidence=event.programme_evidence,
                pls_fit=event.pls_fit.value,
                ecm_accredited=event.ecm_accredited,
                ecm_credits=event.ecm_credits,
                accredited_professions=event.accredited_professions,
                registration_status=event.registration_status,
                registration_deadline=_naive(event.registration_deadline),
                early_registration_deadline=_naive(event.early_registration_deadline),
                fee=event.fee,
                first_seen_at=now,
                last_seen_at=now,
                extraction_confidence=event.extraction_confidence,
                relevance_score=event.relevance_score,
                why_relevant=event.why_relevant,
                is_national_pls_congress=event.is_national_pls_congress,
                dedup_key=key,
            ),
        )
        await self.session.flush()

    async def upcoming(self, today: date) -> list[Event]:
        """Every stored event that has not yet happened."""
        rows = (
            await self.session.execute(
                select(EventRow)
                .where(EventRow.start_date >= _naive(today))
                .order_by(EventRow.start_date),
            )
        ).scalars().all()
        return [_row_to_event(row) for row in rows]


def _row_to_event(row: EventRow) -> Event:
    return Event(
        source_id=row.source_id,
        title=row.title,
        promoter=row.promoter,
        organiser=row.organiser,
        detail_url=row.detail_url,
        programme_url=row.programme_url,
        source_urls=list(row.source_urls or []),
        start_date=row.start_date.date(),
        end_date=row.end_date.date() if row.end_date else None,
        city=row.city,
        region=row.region,
        venue=row.venue,
        event_format=EventFormat(row.event_format),
        stated_audience=row.stated_audience,
        programme_evidence=list(row.programme_evidence or []),
        pls_fit=PLSFit(row.pls_fit),
        ecm_accredited=row.ecm_accredited,
        ecm_credits=row.ecm_credits,
        accredited_professions=list(row.accredited_professions or []),
        registration_status=row.registration_status,
        registration_deadline=(
            row.registration_deadline.date() if row.registration_deadline else None
        ),
        early_registration_deadline=(
            row.early_registration_deadline.date()
            if row.early_registration_deadline
            else None
        ),
        fee=row.fee,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        extraction_confidence=row.extraction_confidence,
        relevance_score=row.relevance_score,
        why_relevant=row.why_relevant,
        is_national_pls_congress=row.is_national_pls_congress,
    )


async def refresh_events(
    session: AsyncSession,
    settings: Settings,
    client: LLMClient,
    offset: int = 0,
) -> CrawlHealth:
    """Crawl the scheduled registry rows and persist what they yield."""
    sources = list(get_event_sources(settings.event_registry))
    if not sources:
        logger.warning("Event registry is empty - skipping event crawl")
        return CrawlHealth()

    scheduled = select_for_run(sources, settings.max_event_sources_per_run, offset=offset)
    repo = EventRepository(session)
    resolved = await repo.resolved_urls()

    events, health = await crawl_sources(scheduled, client, resolved=resolved)

    for source_id, url in health.discovered.items():
        await repo.remember_listing(source_id, url)
    for failure in health.failed:
        await repo.record_failure(failure.split(" ", 1)[0].split(":")[0])

    for event in events:
        await repo.upsert(event)
    await session.commit()

    logger.info("Event refresh complete: %s", health.summary())
    return health


async def events_for_issue(
    session: AsyncSession,
    settings: Settings,
    today: date | None = None,
) -> list[Event]:
    """The events that belong in this week's issue, or an empty list."""
    if not settings.events_enabled:
        return []
    today = today or datetime.now(UTC).date()
    stored = await EventRepository(session).upcoming(today)
    return select_events(stored, today, max_events=settings.max_events)
