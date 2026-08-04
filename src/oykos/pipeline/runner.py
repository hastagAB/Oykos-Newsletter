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
from oykos.db.tables import Base
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
