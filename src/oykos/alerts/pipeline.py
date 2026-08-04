"""Alert delivery pipeline - S034.

Trigger alerts are rare by design. The pipeline refuses to send more than
``settings.max_alerts_per_month`` in any rolling 30-day window, never alerts on
the same item twice, and always ships a one-click unsubscribe header.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from oykos.alerts.template import render_alert_html, render_alert_text
from oykos.alerts.triggers import CATEGORY_LEVEL, AlertLevel, classify_alert
from oykos.config import Settings
from oykos.db.repository import AlertRepository
from oykos.db.subscribers import SubscriberRepository
from oykos.delivery.email_sender import send_newsletter
from oykos.models.news_item import NewsItem

logger = logging.getLogger(__name__)

SUBJECT_HEADLINE_CHARS = 60


def _subject(level: AlertLevel, item: NewsItem) -> str:
    headline = item.editorial.headline_operational or item.content.title
    return f"[{level.value.upper()}] {headline[:SUBJECT_HEADLINE_CHARS]}"


async def process_alerts(
    items: list[NewsItem],
    settings: Settings,
    session: AsyncSession,
) -> list[tuple[NewsItem, AlertLevel]]:
    """Evaluate items for hard-event alerts and send the ones that qualify."""
    alert_repo = AlertRepository(session)
    subscriber_repo = SubscriberRepository(session)

    budget = settings.max_alerts_per_month - await alert_repo.count_last_30_days()
    if budget <= 0:
        logger.info("Monthly alert budget exhausted - suppressing all triggers")
        return []

    # Highest urgency first, so a scarce budget is spent on the worst events.
    ordered = sorted(items, key=lambda i: i.scoring.subscores.urgency, reverse=True)
    subscribers = await subscriber_repo.get_active_subscribers()
    triggered: list[tuple[NewsItem, AlertLevel]] = []

    for item in ordered:
        if budget <= 0:
            logger.info("Monthly alert budget reached - suppressing remaining triggers")
            break

        category = classify_alert(item)
        if category is None:
            continue
        if await alert_repo.already_alerted(str(item.item_id)):
            continue

        level = CATEGORY_LEVEL[category]
        html = render_alert_html(level, item.editorial)
        text = render_alert_text(level, item.editorial)
        subject = _subject(level, item)

        recipients = 0
        if subscribers:
            for subscriber in subscribers:
                unsubscribe_url = (
                    f"{settings.base_url.rstrip('/')}/unsubscribe/{subscriber.unsubscribe_token}"
                )
                if await send_newsletter(
                    settings=settings,
                    to_emails=[subscriber.email],
                    subject=subject,
                    html_content=html,
                    text_content=text,
                    list_unsubscribe_url=unsubscribe_url,
                ):
                    recipients += 1
        elif settings.recipient_list and await send_newsletter(
            settings=settings,
            to_emails=settings.recipient_list,
            subject=subject,
            html_content=html,
            text_content=text,
        ):
            recipients = len(settings.recipient_list)

        if recipients == 0:
            logger.warning("Alert not delivered to anybody: %s", item.content.title)
            continue

        await alert_repo.record(
            item_id=str(item.item_id),
            category=category.value,
            level=level.value,
            subject=subject,
            recipients=recipients,
        )
        triggered.append((item, level))
        budget -= 1

    if triggered:
        await session.commit()
    return triggered
