"""Pipeline entry points - database wiring plus the daily and weekly flows.

The blueprint operating rhythm:

* Monday to Friday: :func:`run_daily` ingests, classifies, scores, gates and
  evaluates trigger alerts. It never sends the newsletter.
* Once a week: :func:`run_weekly` composes, review-gates and delivers the issue.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.config import Settings
from oykos.db.clicks import ClickRepository
from oykos.db.repository import NewsletterRepository
from oykos.db.tables import Base
from oykos.models.taxonomy import IssueStatus
from oykos.observability.logging import setup_logging
from oykos.pipeline.daily import run_daily_pipeline
from oykos.pipeline.weekly import run_weekly_pipeline, send_approved_issues

logger = logging.getLogger("oykos.runner")

HEALTHCHECK_TIMEOUT_SECONDS = 10.0


@asynccontextmanager
async def _session_scope(settings: Settings) -> AsyncGenerator[AsyncSession]:
    """Create the schema if needed and yield a session, disposing the engine after."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


async def _ping_healthcheck(settings: Settings) -> None:
    if not settings.healthcheck_ping_url:
        return
    try:
        async with httpx.AsyncClient(timeout=HEALTHCHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(settings.healthcheck_ping_url)
            logger.info("Healthcheck ping: %d", response.status_code)
    except httpx.HTTPError:
        logger.warning("Healthcheck ping failed", exc_info=True)


async def run_daily(settings: Settings | None = None) -> None:
    """Daily ingestion run (Mon-Fri). Does not send the newsletter."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)
    async with _session_scope(settings) as session:
        await run_daily_pipeline(session, settings)
    await _ping_healthcheck(settings)


async def run_weekly(settings: Settings | None = None) -> None:
    """Weekly composition and delivery run."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)
    async with _session_scope(settings) as session:
        await run_weekly_pipeline(session, settings)
    await _ping_healthcheck(settings)


async def run_pipeline(settings: Settings | None = None) -> None:
    """Convenience run: refresh the candidate pool, then compose and deliver."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)
    async with _session_scope(settings) as session:
        await run_daily_pipeline(session, settings)
        await run_weekly_pipeline(session, settings)
    await _ping_healthcheck(settings)


async def send_pending(settings: Settings | None = None) -> None:
    """Deliver issues an editor approved since the last delivery run."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)
    async with _session_scope(settings) as session:
        sent = await send_approved_issues(session, settings)
    logger.info("Delivered %d approved issue(s)", len(sent))
    await _ping_healthcheck(settings)


async def print_report(week: str | None = None, settings: Settings | None = None) -> None:
    """Print the measurement indicators for one issue.

    Open rate is absent on purpose: Apple Mail Privacy Protection pre-fetches
    images, so it measures the mail client rather than the reader.
    """
    settings = settings or Settings()  # type: ignore[call-arg]
    async with _session_scope(settings) as session:
        repo = NewsletterRepository(session)
        issue = (
            await repo.get_by_week(week)
            if week
            else next(iter(await repo.list_by_status(IssueStatus.SENT)), None)
        )
        if issue is None:
            print(f"No issue found for {week or 'the most recent send'}")  # noqa: T201
            return

        report = await ClickRepository(session).report(str(issue.issue_id))

    if report is None:
        print("No data for that issue")  # noqa: T201
        return

    print(f"\n{report.week}")  # noqa: T201
    print(f"  inviate            {report.sent}")  # noqa: T201
    print(f"  lettori con clic   {report.unique_clickers}  ({report.click_rate:.1%})")  # noqa: T201
    print(f"  clic sulle fonti   {report.source_clicks}")  # noqa: T201
    print(f"  clic sulla CTA     {report.cta_clicks}")  # noqa: T201
    print(f"  ritorno successivo {report.returning}")  # noqa: T201
    print(f"  disiscrizioni      {report.unsubscribes}")  # noqa: T201

    if report.ab_element != "none":
        print(f"\n  test A/B su: {report.ab_element}")  # noqa: T201
        for variant in report.variants:
            print(  # noqa: T201
                f"    {variant.group}  inviate {variant.sent:>4}  "
                f"clic {variant.unique_clickers:>4}  ({variant.click_rate:.1%})",
            )
    print()  # noqa: T201
