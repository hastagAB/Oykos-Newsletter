"""Alert delivery pipeline - S034."""
from __future__ import annotations

import logging

from oykos.alerts.template import render_alert_html, render_alert_text
from oykos.alerts.triggers import AlertLevel, evaluate_alert_triggers
from oykos.config import Settings
from oykos.delivery.email_sender import send_newsletter
from oykos.models.news_item import NewsItem

logger = logging.getLogger(__name__)


async def process_alerts(
    items: list[NewsItem],
    settings: Settings,
) -> list[tuple[NewsItem, AlertLevel]]:
    """Evaluate items for alerts and send if triggered."""
    triggered: list[tuple[NewsItem, AlertLevel]] = []

    for item in items:
        level = evaluate_alert_triggers(item)
        if level is None:
            continue

        triggered.append((item, level))
        logger.info("Alert triggered [%s]: %s", level.value, item.content.title)

        # Render alert email
        html = render_alert_html(level, item.editorial)
        text = render_alert_text(level, item.editorial)
        subject = f"[{level.value.upper()}] {item.editorial.headline_operational[:60]}"

        # Send alert
        recipients = settings.recipient_list
        if recipients:
            await send_newsletter(
                settings=settings,
                to_emails=recipients,
                subject=subject,
                html_content=html,
                text_content=text,
            )

    return triggered
