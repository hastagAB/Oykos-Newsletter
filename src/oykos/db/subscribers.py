"""Subscriber repository - CRUD for subscriber management."""
from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.tables import FeedbackRow, SubscriberRow


def _generate_token() -> str:
    return secrets.token_urlsafe(32)


def _generate_referral_code() -> str:
    return secrets.token_urlsafe(8)[:12]


class SubscriberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, email: str, name: str = "", referred_by: str | None = None) -> SubscriberRow:
        """Create a new subscriber in pending_confirmation status."""
        row = SubscriberRow(
            email=email.lower().strip(),
            name=name,
            status="pending_confirmation",
            confirm_token=_generate_token(),
            unsubscribe_token=_generate_token(),
            referral_code=_generate_referral_code(),
            referred_by=referred_by,
            consented_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
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
        row.confirmed_at = datetime.utcnow()
        await self.session.flush()

        # Credit referrer
        if row.referred_by:
            referrer_stmt = (
                update(SubscriberRow)
                .where(SubscriberRow.subscriber_id == row.referred_by)
                .values(referral_count=SubscriberRow.referral_count + 1)
            )
            await self.session.execute(referrer_stmt)
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
        row.unsubscribed_at = datetime.utcnow()
        await self.session.flush()
        return row

    async def get_by_email(self, email: str) -> SubscriberRow | None:
        stmt = select(SubscriberRow).where(SubscriberRow.email == email.lower().strip())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> SubscriberRow | None:
        stmt = select(SubscriberRow).where(SubscriberRow.referral_code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def count_active(self) -> int:
        stmt = select(func.count()).select_from(SubscriberRow).where(SubscriberRow.status == "active")
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

    async def save(self, issue_id: str, rating: int, comment: str = "", subscriber_id: str | None = None) -> None:
        row = FeedbackRow(
            issue_id=issue_id,
            subscriber_id=subscriber_id,
            rating=rating,
            comment=comment,
        )
        self.session.add(row)
        await self.session.flush()

    async def get_average_rating(self, issue_id: str) -> float | None:
        stmt = select(func.avg(FeedbackRow.rating)).where(FeedbackRow.issue_id == issue_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
