"""SMTP email delivery - S028/S029.

Provider-agnostic: point ``SMTP_HOST``/``SMTP_PORT`` at Zoho, Gmail, or any
other SMTP server. Port 465 uses implicit SSL, anything else uses STARTTLS.

Deliverability is a hard constraint of the blueprint: one-click unsubscribe per
RFC 8058, plus SPF/DKIM/DMARC on the sending domain (DNS side, see
docs/deliverability.md). Recipients are never disclosed to each other.
"""
from __future__ import annotations

import asyncio
import logging
import smtplib
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from oykos.config import Settings

logger = logging.getLogger(__name__)

IMPLICIT_SSL_PORT = 465
SMTP_TIMEOUT_SECONDS = 60


@dataclass
class OutboundMessage:
    """One rendered message bound for one recipient."""

    to_email: str
    subject: str
    html_content: str
    text_content: str
    list_unsubscribe_url: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def build_message(
    settings: Settings,
    to_emails: list[str],
    subject: str,
    html_content: str,
    text_content: str,
    list_unsubscribe_url: str = "",
) -> MIMEMultipart:
    """Build the MIME message, including deliverability headers."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.newsletter_title} <{settings.resolved_sender}>"
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    # Never disclose the subscriber list: a single recipient goes in To,
    # a batch goes in Bcc with an undisclosed-recipients To header.
    if len(to_emails) == 1:
        msg["To"] = to_emails[0]
    else:
        msg["To"] = f"{settings.newsletter_title} <{settings.resolved_sender}>"
        msg["Bcc"] = ", ".join(to_emails)

    unsubscribe_targets: list[str] = []
    if list_unsubscribe_url:
        unsubscribe_targets.append(f"<{list_unsubscribe_url}>")
    if settings.unsubscribe_mailto:
        unsubscribe_targets.append(f"<mailto:{settings.unsubscribe_mailto}?subject=unsubscribe>")
    if unsubscribe_targets:
        msg["List-Unsubscribe"] = ", ".join(unsubscribe_targets)
        if list_unsubscribe_url:
            # RFC 8058 one-click. Only valid alongside an HTTPS target.
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    msg["List-Id"] = f"{settings.newsletter_title} <oykos.{settings.base_url.split('//')[-1]}>"

    msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))
    return msg


def connect(settings: Settings) -> smtplib.SMTP:
    """Open an authenticated SMTP connection, SSL or STARTTLS as configured."""
    if settings.smtp_use_ssl or settings.smtp_port == IMPLICIT_SSL_PORT:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS,
        )
    else:
        server = smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS,
        )
        server.ehlo()
        server.starttls()
        server.ehlo()

    server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
    return server


def _send_sync(settings: Settings, to_emails: list[str], raw_message: str) -> None:
    with connect(settings) as server:
        server.sendmail(settings.resolved_sender, to_emails, raw_message)


async def send_newsletter(
    settings: Settings,
    to_emails: list[str],
    subject: str,
    html_content: str,
    text_content: str,
    list_unsubscribe_url: str = "",
) -> bool:
    """Send a single message. Use :func:`send_bulk` for a subscriber batch."""
    if not to_emails:
        logger.warning("send_newsletter called with no recipients")
        return False

    try:
        msg = build_message(
            settings=settings,
            to_emails=to_emails,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            list_unsubscribe_url=list_unsubscribe_url,
        )
        # smtplib is blocking; keep the event loop free.
        await asyncio.to_thread(_send_sync, settings, to_emails, msg.as_string())
    except Exception:
        logger.exception("Failed to send newsletter email")
        return False

    logger.info("Email sent: recipients=%d", len(to_emails))
    return True


def _send_batch_sync(settings: Settings, messages: list[OutboundMessage]) -> int:
    """Send a batch over as few connections as the provider limits allow.

    Zoho throttles both messages per connection and messages per hour, so the
    connection is recycled every ``smtp_max_per_connection`` messages and each
    send is paced by ``smtp_throttle_seconds``. A single failed recipient does
    not abort the run.
    """
    delivered = 0
    server: smtplib.SMTP | None = None
    sent_on_connection = 0

    try:
        for index, message in enumerate(messages):
            if server is None or sent_on_connection >= settings.smtp_max_per_connection:
                if server is not None:
                    _close(server)
                server = connect(settings)
                sent_on_connection = 0

            msg = build_message(
                settings=settings,
                to_emails=[message.to_email],
                subject=message.subject,
                html_content=message.html_content,
                text_content=message.text_content,
                list_unsubscribe_url=message.list_unsubscribe_url,
            )
            for key, value in message.headers.items():
                msg[key] = value

            try:
                server.sendmail(settings.resolved_sender, [message.to_email], msg.as_string())
                delivered += 1
                sent_on_connection += 1
            except smtplib.SMTPRecipientsRefused:
                logger.warning("Recipient refused, skipping: %s", message.to_email)
            except smtplib.SMTPServerDisconnected:
                logger.warning("SMTP disconnected, reconnecting")
                server = None
                sent_on_connection = 0

            is_last = index == len(messages) - 1
            if settings.smtp_throttle_seconds > 0 and not is_last:
                time.sleep(settings.smtp_throttle_seconds)
    finally:
        if server is not None:
            _close(server)

    return delivered


def _close(server: smtplib.SMTP) -> None:
    try:
        server.quit()
    except smtplib.SMTPException:
        server.close()


async def send_bulk(settings: Settings, messages: list[OutboundMessage]) -> int:
    """Send a batch of per-recipient messages. Returns how many were delivered."""
    if not messages:
        return 0

    try:
        delivered = await asyncio.to_thread(_send_batch_sync, settings, messages)
    except Exception:
        logger.exception("SMTP batch send failed")
        return 0

    logger.info("Batch send: %d/%d delivered", delivered, len(messages))
    return delivered
