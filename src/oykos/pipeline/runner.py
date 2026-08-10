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
from oykos.db.repository import NewsItemRepository, NewsletterRepository
from oykos.db.schema import init_schema
from oykos.events.pipeline import events_for_issue, refresh_events
from oykos.llm.client import LLMClient
from oykos.llm.editorial_qa import audit_issue
from oykos.models.taxonomy import IssueStatus
from oykos.newsletter.compliance import check_issue
from oykos.newsletter.template import event_view
from oykos.observability.logging import setup_logging
from oykos.pipeline.daily import classify_and_score, run_daily_pipeline
from oykos.pipeline.weekly import run_weekly_pipeline, send_approved_issues
from oykos.processing.scoring import detect_penalties

logger = logging.getLogger("oykos.runner")

HEALTHCHECK_TIMEOUT_SECONDS = 10.0


@asynccontextmanager
async def _session_scope(settings: Settings) -> AsyncGenerator[AsyncSession]:
    """Create the schema if needed and yield a session, disposing the engine after."""
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with engine.begin() as conn:
            await init_schema(conn, settings.database_url)
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


async def run_weekly(
    settings: Settings | None = None,
    *,
    rewrite: bool = False,
    week: str | None = None,
) -> None:
    """Weekly composition and delivery run."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)
    async with _session_scope(settings) as session:
        await run_weekly_pipeline(session, settings, rewrite=rewrite, week=week)
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


async def rescore(days: int = 14, settings: Settings | None = None) -> None:
    """Re-classify and re-score stored items with the current model.

    Ingestion deduplicates, so items already in the database keep whatever
    scores the model of the day gave them. Without this, changing the scoring
    rules has no effect on anything already ingested.
    """
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)

    async with _session_scope(settings) as session:
        repo = NewsItemRepository(session)
        items = await repo.get_recent(days=days)
        logger.info("Re-scoring %d item(s) ingested in the last %d days", len(items), days)
        # Penalties detectable from the raw item are recomputed too, so a
        # rescore is a full refresh rather than a partial one.
        recent_titles: list[str] = []
        for item in items:
            item.scoring.penalties = detect_penalties(item, recent_titles)
            recent_titles.append(item.content.title)

        processed = await classify_and_score(items, LLMClient(settings), repo, limit=len(items))
        await session.commit()

    logger.info("Re-scored %d item(s)", len(processed))


async def print_qa(week: str | None = None, settings: Settings | None = None) -> None:
    """Audit an issue against the editorial guidelines and print the findings."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)

    async with _session_scope(settings) as session:
        repo = NewsletterRepository(session)
        issue = await repo.get_by_week(week) if week else None
        if issue is None:
            for status in (IssueStatus.IN_REVIEW, IssueStatus.APPROVED, IssueStatus.SENT):
                found = await repo.list_by_status(status)
                if found:
                    issue = found[0]
                    break
        if issue is None:
            print("Nessun numero da controllare")  # noqa: T201
            return
        report = await audit_issue(issue, LLMClient(settings))

    print(f"\n{issue.week}  verdetto: {report.verdict}")  # noqa: T201
    print(f"  articoli senza azione: {report.items_without_action}/{len(issue.slots)}")  # noqa: T201
    if report.summary:
        print(f"  {report.summary}")  # noqa: T201
    for finding in report.findings:
        print(f"\n  [{finding.rule}] {finding.item_title}")  # noqa: T201
        print(f"    testo:    {finding.offending_text}")  # noqa: T201
        print(f"    problema: {finding.why}")  # noqa: T201
        if finding.suggested_rewrite:
            print(f"    proposta: {finding.suggested_rewrite}")  # noqa: T201
    print()  # noqa: T201


async def print_compliance(week: str | None = None, settings: Settings | None = None) -> None:
    """Deterministic guideline check of an issue. Same issue, same answer."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)

    async with _session_scope(settings) as session:
        repo = NewsletterRepository(session)
        issue = await repo.get_by_week(week) if week else None
        if issue is None:
            for status in (IssueStatus.IN_REVIEW, IssueStatus.APPROVED, IssueStatus.SENT):
                found = await repo.list_by_status(status)
                if found:
                    issue = found[0]
                    break
        if issue is None:
            print("Nessun numero da controllare")  # noqa: T201
            return

    result = check_issue(issue)
    verdict = "CONFORME" if result.passed else "NON CONFORME"
    print(f"\n{issue.week}  linee guida v2.0: {verdict}")  # noqa: T201
    print(f"  articoli: {len(issue.slots)}  violazioni: {len(result.failures)}")  # noqa: T201
    for failure in result.failures:
        print(f"  [X] {failure}")  # noqa: T201
    print("\n  Da verificare a mano prima dell'invio:")  # noqa: T201
    for check in result.human_checks:
        print(f"  [ ] {check}")  # noqa: T201
    print()  # noqa: T201


async def print_events(offset: int = 0, settings: Settings | None = None) -> None:
    """Crawl the scheduled event sources and show what the section would contain."""
    settings = settings or Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)

    async with _session_scope(settings) as session:
        client = LLMClient(settings)
        health = await refresh_events(session, settings, client, offset=offset)
        events = await events_for_issue(session, settings)

    print(f"\ncrawl: {health.summary()}")  # noqa: T201
    for failure in health.failed[:10]:
        print(f"  failed: {failure}")  # noqa: T201
    for source_id, url in list(health.discovered.items())[:10]:
        print(f"  discovered: {source_id} -> {url}")  # noqa: T201

    print(f"\n{len(events)} event(s) would be shown:\n")  # noqa: T201
    for event in events:
        view = event_view(event)
        where = f" - {view['where']}" if view["where"] else ""
        print(f"  {view['when']}{where}: {view['title']}")  # noqa: T201
        print(f"     fit={event.pls_fit.value} score={event.relevance_score}")  # noqa: T201
        if event.stated_audience:
            print(f"     audience: {event.stated_audience[:90]}")  # noqa: T201
        if view["why"]:
            print(f"     {view['why']}")  # noqa: T201
        print(f"     {view['url']}")  # noqa: T201
    print()  # noqa: T201


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
