"""Tests for the measurement indicators - guidelines section 11.

These cover the arithmetic an editor will make decisions on. A click report that
double counts, or that keeps counting people who asked to be erased, is worse
than no report: it invites confident wrong conclusions.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.db.clicks import ClickRepository
from oykos.db.subscribers import SubscriberRepository
from oykos.db.tables import Base, ClickEventRow, NewsletterRow, SubscriberRow


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _issue(
    session: AsyncSession,
    *,
    issue_id: str = "issue-1",
    week: str = "2026-W32",
    sent: int = 100,
    ab_element: str = "none",
) -> None:
    session.add(
        NewsletterRow(
            issue_id=issue_id,
            week=week,
            subject_line="Oggetto",
            preheader="",
            status="sent",
            sent_at=datetime(2026, 8, 3, 8, 0),  # noqa: DTZ001 - column stores naive UTC
            sent_count=sent,
            ab_element=ab_element,
        ),
    )
    await session.flush()


async def _click(
    session: AsyncSession,
    subscriber_id: str,
    *,
    issue_id: str = "issue-1",
    week: str = "2026-W32",
    kind: str = "source",
    ab_group: str = "A",
) -> None:
    await ClickRepository(session).record(
        issue_id=issue_id,
        subscriber_id=subscriber_id,
        week=week,
        kind=kind,
        target_url="https://www.salute.gov.it/x",
        ab_group=ab_group,
    )


@pytest.mark.asyncio
async def test_unknown_issue_reports_nothing(session: AsyncSession) -> None:
    assert await ClickRepository(session).report("does-not-exist") is None


@pytest.mark.asyncio
async def test_one_reader_clicking_five_links_is_one_clicker(session: AsyncSession) -> None:
    """Unique clicks is the indicator. Total clicks flatter the sender."""
    await _issue(session)
    for _ in range(5):
        await _click(session, "sub-1")

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.unique_clickers == 1
    assert report.source_clicks == 5
    assert report.click_rate == pytest.approx(0.01)


@pytest.mark.asyncio
async def test_source_and_cta_clicks_are_counted_separately(session: AsyncSession) -> None:
    await _issue(session)
    await _click(session, "sub-1", kind="source")
    await _click(session, "sub-2", kind="cta")
    await _click(session, "sub-3", kind="cta")

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.source_clicks == 1
    assert report.cta_clicks == 2
    assert report.unique_clickers == 3


@pytest.mark.asyncio
async def test_returning_counts_only_readers_who_came_back_later(session: AsyncSession) -> None:
    """Return in the following weeks - not clicks within the same issue."""
    await _issue(session)
    await _click(session, "sub-1")
    await _click(session, "sub-2")
    # sub-1 comes back the week after; sub-2 does not.
    await _click(session, "sub-1", issue_id="issue-2", week="2026-W33")

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.returning == 1


@pytest.mark.asyncio
async def test_an_earlier_week_is_not_a_return(session: AsyncSession) -> None:
    await _issue(session)
    await _click(session, "sub-1")
    await _click(session, "sub-1", issue_id="issue-0", week="2026-W31")

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.returning == 0


@pytest.mark.asyncio
async def test_unsubscribes_after_the_send_are_attributed_to_the_issue(
    session: AsyncSession,
) -> None:
    await _issue(session)
    sent_at = datetime(2026, 8, 3, 8, 0)  # noqa: DTZ001 - column stores naive UTC
    session.add(
        SubscriberRow(
            email="before@example.it",
            confirm_token="c1",
            unsubscribe_token="u1",
            status="unsubscribed",
            unsubscribed_at=sent_at - timedelta(days=2),
        ),
    )
    session.add(
        SubscriberRow(
            email="after@example.it",
            confirm_token="c2",
            unsubscribe_token="u2",
            status="unsubscribed",
            unsubscribed_at=sent_at + timedelta(hours=3),
        ),
    )
    await session.flush()

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.unsubscribes == 1


@pytest.mark.asyncio
async def test_ab_variants_split_by_group(session: AsyncSession) -> None:
    await _issue(session, ab_element="subject")
    for index in range(6):
        group = "A" if index % 2 == 0 else "B"
        session.add(
            SubscriberRow(
                email=f"r{index}@example.it",
                confirm_token=f"c{index}",
                unsubscribe_token=f"u{index}",
                status="active",
                ab_group=group,
            ),
        )
    await session.flush()
    # Two of the three B readers click; one of the three A readers clicks.
    await _click(session, "sub-a1", ab_group="A")
    await _click(session, "sub-b1", ab_group="B")
    await _click(session, "sub-b2", ab_group="B")

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.ab_element == "subject"
    variants = {variant.group: variant for variant in report.variants}
    assert variants["A"].unique_clickers == 1
    assert variants["B"].unique_clickers == 2


@pytest.mark.asyncio
async def test_no_variants_reported_when_no_test_is_running(session: AsyncSession) -> None:
    await _issue(session, ab_element="none")
    await _click(session, "sub-1")

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.variants == []


@pytest.mark.asyncio
async def test_erasure_deletes_click_history(session: AsyncSession) -> None:
    """A click record ties a person to what they read. Erasure must remove it."""
    repo = SubscriberRepository(session)
    subscriber = await repo.create("reader@example.it")
    await _click(session, subscriber.subscriber_id)
    assert (await session.execute(select(ClickEventRow))).scalars().all()

    assert await repo.delete_subscriber_data("reader@example.it") is True

    remaining = (await session.execute(select(ClickEventRow))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_erasure_leaves_other_readers_clicks_alone(session: AsyncSession) -> None:
    repo = SubscriberRepository(session)
    erased = await repo.create("gone@example.it")
    kept = await repo.create("stays@example.it")
    await _click(session, erased.subscriber_id)
    await _click(session, kept.subscriber_id)

    await repo.delete_subscriber_data("gone@example.it")

    remaining = (await session.execute(select(ClickEventRow))).scalars().all()
    assert [row.subscriber_id for row in remaining] == [kept.subscriber_id]


@pytest.mark.asyncio
async def test_click_rate_is_zero_when_nothing_was_sent(session: AsyncSession) -> None:
    """Guards the divide-by-zero on an issue that was composed but never delivered."""
    await _issue(session, sent=0)

    report = await ClickRepository(session).report("issue-1")

    assert report is not None
    assert report.click_rate == 0.0


@pytest.mark.asyncio
async def test_clicks_recorded_at_are_naive_utc(session: AsyncSession) -> None:
    """The DB stores naive UTC; an aware value here would poison week comparisons."""
    await _issue(session)
    await _click(session, "sub-1")

    row = (await session.execute(select(ClickEventRow))).scalars().one()

    assert row.clicked_at.tzinfo is None
    assert abs((row.clicked_at - datetime.now(UTC).replace(tzinfo=None)).total_seconds()) < 60
