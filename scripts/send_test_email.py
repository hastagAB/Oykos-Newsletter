"""Quick test: send a sample newsletter email via Gmail SMTP."""
import asyncio

from oykos.config import Settings
from oykos.delivery.email_sender import send_newsletter


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><title>Test Newsletter</title></head>
<body style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
  <div style="background: #1a5276; color: #fff; padding: 20px;">
    <h1 style="margin:0;">L'Essenziale in Pediatria</h1>
    <p style="margin:4px 0 0; opacity:.85;">Test Email - 2026-W18</p>
  </div>
  <div style="padding: 20px;">
    <h2>Oykos Newsletter Engine - Test</h2>
    <p>If you are reading this, the Gmail SMTP delivery pipeline is working correctly.</p>
    <ul>
      <li>Azure OpenAI integration: configured</li>
      <li>Gmail SMTP delivery: working</li>
      <li>127 tests passing</li>
    </ul>
    <p style="color: #888; font-size: 12px;">This is an automated test from the Oykos Newsletter Engine.</p>
  </div>
</body>
</html>"""

SAMPLE_TEXT = """L'Essenziale in Pediatria - Test Email - 2026-W18
==================================================

Oykos Newsletter Engine - Test

If you are reading this, the Gmail SMTP delivery pipeline is working correctly.

- Azure OpenAI integration: configured
- Gmail SMTP delivery: working
- 127 tests passing
"""


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    print(f"Sending test email from {settings.resolved_sender} to {settings.recipient_list}")

    ok = await send_newsletter(
        settings=settings,
        to_emails=settings.recipient_list,
        subject="[TEST] L'Essenziale in Pediatria - Pipeline Funzionante",
        html_content=SAMPLE_HTML,
        text_content=SAMPLE_TEXT,
    )
    print(f"Result: {'SUCCESS' if ok else 'FAILED'}")


if __name__ == "__main__":
    asyncio.run(main())
