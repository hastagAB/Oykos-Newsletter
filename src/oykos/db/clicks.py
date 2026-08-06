"""Click recording and the indicator report (guidelines section 11)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.tables import ClickEventRow, NewsletterRow, SubscriberRow


@dataclass
class VariantResult:
    group: str
    sent: int = 0
    unique_clickers: int = 0

    @property
    def click_rate(self) -> float:
        return self.unique_clickers / self.sent if self.sent else 0.0


@dataclass
class IssueReport:
    week: str
    sent: int = 0
    unique_clickers: int = 0
    source_clicks: int = 0
    cta_clicks: int = 0
    unsubscribes: int = 0
    returning: int = 0
    ab_element: str = "none"
    variants: list[VariantResult] = field(default_factory=list)

    @property
    def click_rate(self) -> float:
        return self.unique_clickers / self.sent if self.sent else 0.0


class ClickRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        issue_id: str,
        subscriber_id: str,
        week: str,
        kind: str,
        target_url: str,
        ab_group: str,
    ) -> None:
        self.session.add(
            ClickEventRow(
                issue_id=issue_id,
                subscriber_id=subscriber_id,
                week=week,
                kind=kind,
                target_url=target_url,
                ab_group=ab_group,
                clicked_at=datetime.now(UTC).replace(tzinfo=None),
            ),
        )
        await self.session.flush()

    async def _clickers(self, issue_id: str) -> set[str]:
        result = await self.session.execute(
            select(ClickEventRow.subscriber_id)
            .where(ClickEventRow.issue_id == issue_id)
            .distinct(),
        )
        return {row[0] for row in result.all()}

    async def report(self, issue_id: str) -> IssueReport | None:
        """Indicators for one issue: clicks, return, unsubscribes, variants.

        Open rate is deliberately absent - Apple Mail Privacy Protection makes it
        uninterpretable, so the guidelines treat it as secondary.
        """
        issue = (
            await self.session.execute(
                select(NewsletterRow).where(NewsletterRow.issue_id == issue_id),
            )
        ).scalars().first()
        if issue is None:
            return None

        report = IssueReport(
            week=issue.week,
            sent=issue.sent_count,
            ab_element=issue.ab_element,
        )

        clickers = await self._clickers(issue_id)
        report.unique_clickers = len(clickers)

        for kind, attribute in (("source", "source_clicks"), ("cta", "cta_clicks")):
            count = (
                await self.session.execute(
                    select(func.count())
                    .select_from(ClickEventRow)
                    .where(
                        ClickEventRow.issue_id == issue_id,
                        ClickEventRow.kind == kind,
                    ),
                )
            ).scalar_one()
            setattr(report, attribute, count)

        if issue.sent_at is not None:
            report.unsubscribes = (
                await self.session.execute(
                    select(func.count())
                    .select_from(SubscriberRow)
                    .where(SubscriberRow.unsubscribed_at >= issue.sent_at),
                )
            ).scalar_one()

        # "Return in the following weeks": readers of this issue who also clicked
        # in a later one. The signal the guidelines actually care about.
        if clickers:
            later = (
                await self.session.execute(
                    select(ClickEventRow.subscriber_id)
                    .where(
                        ClickEventRow.week > issue.week,
                        ClickEventRow.subscriber_id.in_(clickers),
                    )
                    .distinct(),
                )
            ).all()
            report.returning = len({row[0] for row in later})

        if issue.ab_element != "none":
            for group in ("A", "B"):
                sent = (
                    await self.session.execute(
                        select(func.count())
                        .select_from(SubscriberRow)
                        .where(
                            SubscriberRow.ab_group == group,
                            SubscriberRow.status == "active",
                        ),
                    )
                ).scalar_one()
                clicked = (
                    await self.session.execute(
                        select(ClickEventRow.subscriber_id)
                        .where(
                            ClickEventRow.issue_id == issue_id,
                            ClickEventRow.ab_group == group,
                        )
                        .distinct(),
                    )
                ).all()
                report.variants.append(
                    VariantResult(group=group, sent=sent, unique_clickers=len(clicked)),
                )

        return report
