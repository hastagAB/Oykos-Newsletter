"""SMTP preflight - verify the provider connection before a real send.

Checks the things that actually go wrong with Zoho, in the order they fail:

1. credentials are configured
2. the host/port/TLS combination connects
3. authentication succeeds
4. the From address is one the account is allowed to send as

Run with ``oykos check-smtp``.
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass

from oykos.config import Settings
from oykos.delivery.email_sender import connect

logger = logging.getLogger(__name__)

IMPLICIT_SSL_PORT = 465
REJECTION_CODE = 400

# Zoho's SMTP host must match the data centre the account was created in.
ZOHO_HOSTS = {
    "smtp.zoho.com": "United States (zoho.com)",
    "smtp.zoho.eu": "Europe (zoho.eu)",
    "smtp.zoho.in": "India (zoho.in)",
    "smtp.zoho.com.au": "Australia (zoho.com.au)",
    "smtp.zoho.jp": "Japan (zoho.jp)",
    "smtp.zohocloud.ca": "Canada (zohocloud.ca)",
}


@dataclass
class CheckResult:
    ok: bool
    summary: str
    hints: list[str]


def _zoho_hints(settings: Settings) -> list[str]:
    if "zoho" not in settings.smtp_host:
        return []
    data_centre = ZOHO_HOSTS.get(settings.smtp_host, "unrecognised host")
    return [
        "Zoho requires an app-specific password when two-factor auth is on. "
        "Create one in Zoho Mail > My Account > Security > App passwords.",
        "SMTP access is not available on the free Zoho Mail plan. "
        "If auth keeps failing on correct credentials, check your plan.",
        f"Confirm the data centre matches your account: {data_centre}. "
        f"Known hosts: {', '.join(sorted(ZOHO_HOSTS))}.",
    ]


def check_smtp(settings: Settings) -> CheckResult:
    """Connect and authenticate without sending anything."""
    if not settings.smtp_username or not settings.smtp_password.get_secret_value():
        return CheckResult(
            ok=False,
            summary="SMTP_USERNAME or SMTP_PASSWORD is not set.",
            hints=["Set both in .env, then re-run."],
        )

    mode = "SSL" if settings.smtp_use_ssl or settings.smtp_port == IMPLICIT_SSL_PORT else "STARTTLS"
    target = f"{settings.smtp_host}:{settings.smtp_port} ({mode}) as {settings.smtp_username}"

    try:
        server = connect(settings)
    except smtplib.SMTPAuthenticationError as exc:
        return CheckResult(
            ok=False,
            summary=f"Authentication rejected by {settings.smtp_host}: {exc.smtp_code}",
            hints=_zoho_hints(settings)
            or ["Check the username and password, and whether the account needs an app password."],
        )
    except (OSError, TimeoutError, smtplib.SMTPException) as exc:
        return CheckResult(
            ok=False,
            summary=f"Could not connect to {target}: {exc}",
            hints=[
                "Port 465 needs SMTP_USE_SSL=true; port 587 needs SMTP_USE_SSL=false.",
                *_zoho_hints(settings),
            ],
        )

    hints: list[str] = []
    try:
        # Probe the envelope sender without delivering: RSET discards it.
        code, message = server.docmd("MAIL", f"FROM:<{settings.resolved_sender}>")
        server.docmd("RSET")
        if code >= REJECTION_CODE:
            hints.append(
                f"The server refused '{settings.resolved_sender}' as a From address "
                f"({code} {message.decode(errors='replace')}). Zoho only allows the "
                "mailbox itself, a verified alias, or an address on a verified domain. "
                "Set SENDER_EMAIL to one of those.",
            )
    except smtplib.SMTPException as exc:
        hints.append(f"Could not verify the From address: {exc}")
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            server.close()

    if hints:
        return CheckResult(ok=False, summary=f"Connected to {target}, but:", hints=hints)

    return CheckResult(
        ok=True,
        summary=f"Connected and authenticated: {target}",
        hints=[f"Sending as: {settings.resolved_sender}"],
    )
