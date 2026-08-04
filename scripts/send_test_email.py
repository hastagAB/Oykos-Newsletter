"""Send one real test email through the configured SMTP provider.

Run `oykos check-smtp` first: it verifies the connection without sending. Use
this script once that passes, to confirm an actual message arrives and renders.

Usage:
    python scripts/send_test_email.py
"""
from __future__ import annotations

import asyncio
import sys

from oykos.config import Settings
from oykos.delivery.email_sender import send_newsletter
from oykos.delivery.preflight import check_smtp

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><title>Test</title></head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #1a5276; color: #fff; padding: 20px;">
    <h1 style="margin:0;">L'Essenziale in Pediatria</h1>
    <p style="margin:4px 0 0; opacity:.85;">Email di prova</p>
  </div>
  <div style="padding: 20px;">
    <h2>Consegna SMTP funzionante</h2>
    <p>Se stai leggendo questo messaggio, la consegna e configurata correttamente.</p>
    <p style="color: #888; font-size: 12px;">
      Messaggio automatico generato da Oykos Newsletter Engine.
    </p>
  </div>
</body>
</html>"""

SAMPLE_TEXT = """L'Essenziale in Pediatria - Email di prova
==========================================

Consegna SMTP funzionante.

Se stai leggendo questo messaggio, la consegna e configurata correttamente.
"""


async def main() -> int:
    settings = Settings()  # type: ignore[call-arg]

    check = check_smtp(settings)
    print(f"Preflight: {check.summary}")  # noqa: T201
    for hint in check.hints:
        print(f"  - {hint}")  # noqa: T201
    if not check.ok:
        return 1

    recipients = settings.recipient_list
    if not recipients:
        print("Set RECIPIENT_EMAILS in .env to receive the test message.")  # noqa: T201
        return 1

    print(f"Sending from {settings.resolved_sender} to {recipients}")  # noqa: T201
    ok = await send_newsletter(
        settings=settings,
        to_emails=recipients,
        subject="[TEST] L'Essenziale in Pediatria",
        html_content=SAMPLE_HTML,
        text_content=SAMPLE_TEXT,
    )
    print("Result: SUCCESS" if ok else "Result: FAILED - check the logs")  # noqa: T201
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
