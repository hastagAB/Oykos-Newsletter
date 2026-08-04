"""Delivery: recipient privacy, deliverability headers, and provider transport.

If these regress, the product either leaks its subscriber list, lands in spam,
or gets throttled by the provider mid-send.
"""
from __future__ import annotations

import smtplib
from unittest.mock import MagicMock

import pytest

from oykos.config import Settings
from oykos.delivery import email_sender
from oykos.delivery.email_sender import OutboundMessage, build_message, send_bulk


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "openai_api_key": "sk-test",
        "smtp_username": "sender@example.it",
        "smtp_password": "pw",
        "base_url": "https://oykos.example.it",
        "smtp_throttle_seconds": 0,
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _build(to: list[str], unsubscribe_url: str = "", **setting_overrides: object):
    return build_message(
        settings=_settings(**setting_overrides),
        to_emails=to,
        subject="Oggetto",
        html_content="<p>ciao</p>",
        text_content="ciao",
        list_unsubscribe_url=unsubscribe_url,
    )


def test_recipients_are_never_disclosed_to_each_other() -> None:
    msg = _build(["one@example.it", "two@example.it"])

    assert "one@example.it" not in msg["To"]
    assert "two@example.it" not in msg["To"]
    assert "one@example.it" in msg["Bcc"]


def test_single_recipient_goes_in_the_to_header() -> None:
    msg = _build(["one@example.it"])

    assert msg["To"] == "one@example.it"
    assert msg["Bcc"] is None


def test_one_click_unsubscribe_per_rfc_8058() -> None:
    msg = _build(["one@example.it"], unsubscribe_url="https://oykos.example.it/unsubscribe/tok")

    assert msg["List-Unsubscribe"] == "<https://oykos.example.it/unsubscribe/tok>"
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_one_click_post_is_omitted_without_an_https_target() -> None:
    """A one-click POST to a mailto: is meaningless, so the header must not appear."""
    msg = _build(["one@example.it"], unsubscribe_mailto="unsub@example.it")

    assert "mailto:unsub@example.it" in msg["List-Unsubscribe"]
    assert msg["List-Unsubscribe-Post"] is None


def test_message_carries_both_parts_and_standard_headers() -> None:
    msg = _build(["one@example.it"])

    assert [part.get_content_subtype() for part in msg.get_payload()] == ["plain", "html"]
    assert msg["Date"]
    assert msg["Message-ID"]
    assert msg["List-Id"]


# ── Provider transport ────────────────────────────────────

def test_legacy_gmail_env_vars_still_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """An existing .env using GMAIL_* keeps working after the rename."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GMAIL_ADDRESS", "legacy@example.it")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "legacy-pw")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.smtp_username == "legacy@example.it"
    assert settings.smtp_password.get_secret_value() == "legacy-pw"
    assert settings.resolved_sender == "legacy@example.it"


def test_port_465_uses_implicit_ssl(monkeypatch: pytest.MonkeyPatch) -> None:
    ssl_server = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP_SSL", MagicMock(return_value=ssl_server))
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(side_effect=AssertionError("used plain SMTP")))

    email_sender.connect(_settings(smtp_host="smtp.zoho.eu", smtp_port=465, smtp_use_ssl=True))

    ssl_server.login.assert_called_once()
    ssl_server.starttls.assert_not_called()


def test_port_587_uses_starttls(monkeypatch: pytest.MonkeyPatch) -> None:
    plain_server = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=plain_server))
    monkeypatch.setattr(
        smtplib, "SMTP_SSL", MagicMock(side_effect=AssertionError("used implicit SSL")),
    )

    email_sender.connect(_settings(smtp_host="smtp.zoho.eu", smtp_port=587, smtp_use_ssl=False))

    plain_server.starttls.assert_called_once()
    plain_server.login.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_send_reuses_one_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zoho throttles per connection, so a batch must not reconnect per message."""
    server = MagicMock()
    connect = MagicMock(return_value=server)
    monkeypatch.setattr(email_sender, "connect", connect)

    messages = [
        OutboundMessage(
            to_email=f"doc{i}@example.it",
            subject="Oggetto",
            html_content="<p>ciao</p>",
            text_content="ciao",
        )
        for i in range(10)
    ]

    delivered = await send_bulk(_settings(), messages)

    assert delivered == 10
    assert connect.call_count == 1
    assert server.sendmail.call_count == 10


@pytest.mark.asyncio
async def test_bulk_send_recycles_the_connection_at_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(email_sender, "connect", connect)

    messages = [
        OutboundMessage(to_email=f"d{i}@e.it", subject="s", html_content="h", text_content="t")
        for i in range(10)
    ]

    await send_bulk(_settings(smtp_max_per_connection=4), messages)

    assert connect.call_count == 3


@pytest.mark.asyncio
async def test_one_refused_recipient_does_not_abort_the_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MagicMock()
    server.sendmail.side_effect = [
        None,
        smtplib.SMTPRecipientsRefused({"bad@example.it": (550, b"no")}),
        None,
    ]
    monkeypatch.setattr(email_sender, "connect", MagicMock(return_value=server))

    messages = [
        OutboundMessage(to_email=e, subject="s", html_content="h", text_content="t")
        for e in ("ok1@example.it", "bad@example.it", "ok2@example.it")
    ]

    assert await send_bulk(_settings(), messages) == 2


@pytest.mark.asyncio
async def test_bulk_send_with_no_messages_is_a_no_op() -> None:
    assert await send_bulk(_settings(), []) == 0
