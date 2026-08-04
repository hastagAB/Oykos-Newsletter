"""Subscriber repository - CRUD for subscriber management."""
from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.repository import utcnow
from oykos.db.tables import FeedbackRow, SubscriberRow


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


class SubscriberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, email: str, name: str = "") -> SubscriberRow:
        """Create a new subscriber in pending_confirmation status."""
        row = SubscriberRow(
            email=email.lower().strip(),
            name=name,
            status="pending_confirmation",
            confirm_token=_generate_token(),
            unsubscribe_token=_generate_token(),
            consented_at=utcnow(),
            created_at=utcnow(),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def confirm(self, token: str) -> SubscriberRow | None:
        """Confirm a subscriber via their confirmation token (double opt-in)."""
        stmt = select(SubscriberRow).where(
            SubscriberRow.confirm_token == token,
            SubscriberRow.status == "pending_confirmation",
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "active"
        row.confirmed_at = utcnow()
        await self.session.flush()
        return row

    async def unsubscribe(self, token: str) -> SubscriberRow | None:
        """Unsubscribe via one-click token (RFC 8058 / GDPR)."""
        stmt = select(SubscriberRow).where(
            SubscriberRow.unsubscribe_token == token,
            SubscriberRow.status == "active",
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = "unsubscribed"
        row.unsubscribed_at = utcnow()
        await self.session.flush()
        return row

    async def get_by_email(self, email: str) -> SubscriberRow | None:
        stmt = select(SubscriberRow).where(SubscriberRow.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_unsubscribe_token(self, token: str) -> SubscriberRow | None:
        """Identity lookup for the preferences page.

        The unsubscribe token is already per-subscriber and unguessable, so it
        doubles as the preferences key. No login required, nothing to phish.
        """
        stmt = select(SubscriberRow).where(SubscriberRow.unsubscribe_token == token)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_preferences(
        self,
        token: str,
        topics: list[str],
        alert_opt_in: bool,
        region: str = "",
    ) -> SubscriberRow | None:
        row = await self.get_by_unsubscribe_token(token)
        if row is None:
            return None
        row.topics = topics
        row.alert_opt_in = alert_opt_in
        row.region = region
        await self.session.flush()
        return row

    async def get_active_emails(self) -> list[str]:
        """Get all confirmed active subscriber emails for sending."""
        stmt = select(SubscriberRow.email).where(SubscriberRow.status == "active")
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]

    async def get_active_subscribers(self) -> list[SubscriberRow]:
        """Get all active subscriber rows (for A/B splitting)."""
        stmt = select(SubscriberRow).where(SubscriberRow.status == "active")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_alert_subscribers(self) -> list[SubscriberRow]:
        """Active subscribers who have not opted out of trigger alerts."""
        stmt = select(SubscriberRow).where(
            SubscriberRow.status == "active",
            SubscriberRow.alert_opt_in.is_(True),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        stmt = (
            select(func.count())
            .select_from(SubscriberRow)
            .where(SubscriberRow.status == "active")
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_subscriber_data(self, email: str) -> bool:
        """GDPR right to erasure - hard delete subscriber record."""
        row = await self.get_by_email(email)
        if row is None:
            return False
        await self.session.delete(row)
        await self.session.flush()
        return True


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(
        self,
        issue_id: str,
        rating: int,
        comment: str = "",
        subscriber_id: str | None = None,
        too_long: bool = False,
        too_many_devices: bool = False,
        not_relevant: bool = False,
    ) -> None:
        row = FeedbackRow(
            issue_id=issue_id,
            subscriber_id=subscriber_id,
            rating=rating,
            comment=comment,
            too_long=too_long,
            too_many_devices=too_many_devices,
            not_relevant=not_relevant,
        )
        self.session.add(row)
        await self.session.flush()

    async def get_average_rating(self, issue_id: str) -> float | None:
        stmt = select(func.avg(FeedbackRow.rating)).where(FeedbackRow.issue_id == issue_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_signal_counts(self, issue_id: str) -> dict[str, int]:
        """How many readers flagged the issue as too long, device-heavy, etc."""
        stmt = select(
            func.count().filter(FeedbackRow.too_long.is_(True)),
            func.count().filter(FeedbackRow.too_many_devices.is_(True)),
            func.count().filter(FeedbackRow.not_relevant.is_(True)),
            func.count(),
        ).where(FeedbackRow.issue_id == issue_id)
        result = await self.session.execute(stmt)
        too_long, too_many_devices, not_relevant, total = result.one()
        return {
            "too_long": int(too_long or 0),
            "too_many_devices": int(too_many_devices or 0),
            "not_relevant": int(not_relevant or 0),
            "total": int(total or 0),
        }
