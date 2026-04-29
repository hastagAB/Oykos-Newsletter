"""Gmail SMTP email delivery - S028/S029."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from oykos.config import Settings

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465


async def send_newsletter(
    settings: Settings,
    to_emails: list[str],
    subject: str,
    html_content: str,
    text_content: str,
    list_unsubscribe_url: str = "",
) -> bool:
    """Send newsletter via Gmail SMTP with app password authentication."""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"L'Essenziale in Pediatria <{settings.resolved_sender}>"
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject

        if list_unsubscribe_url:
            msg["List-Unsubscribe"] = f"<{list_unsubscribe_url}>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        msg.attach(MIMEText(text_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
            server.login(
                settings.gmail_address,
                settings.gmail_app_password.get_secret_value(),
            )
            server.sendmail(settings.resolved_sender, to_emails, msg.as_string())

        logger.info("Email sent via Gmail SMTP: recipients=%d", len(to_emails))
        return True

    except Exception:
        logger.exception("Failed to send newsletter email")
        return False
