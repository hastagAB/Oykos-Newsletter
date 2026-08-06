"""Click tracking for the measurement loop.

The editorial guidelines (section 11) treat clicks as the reliable signal and
open rates as unreliable, because Apple Mail Privacy Protection pre-fetches
images. So there is no tracking pixel here: only real clicks are recorded.

Every tracked link is HMAC-signed. Without a signature the redirect endpoint
would be an open redirect - anyone could send `?url=<phishing>` from our own
domain and inherit its reputation.

Click data is personal data: it links a subscriber to what they read. It is
only collected when CLICK_TRACKING is enabled, and `oykos.db.subscribers`
deletes it on erasure.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import urlparse

SEPARATOR = "."
ALLOWED_SCHEMES = frozenset({"http", "https"})
CLICK_KINDS = frozenset({"source", "cta"})


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return _b64(digest)[:32]


def build_token(
    *,
    issue_id: str,
    subscriber_token: str,
    kind: str,
    url: str,
    secret: str,
) -> str:
    """Opaque, signed token identifying one link in one issue for one reader."""
    payload = _b64(f"{issue_id}|{subscriber_token}|{kind}|{url}".encode())
    return f"{payload}{SEPARATOR}{_sign(payload, secret)}"


def parse_token(token: str, secret: str) -> tuple[str, str, str, str] | None:
    """Return (issue_id, subscriber_token, kind, url), or None if untrustworthy.

    Rejects anything whose signature does not verify, so the endpoint can never
    be used to redirect to an arbitrary destination.
    """
    payload, _, signature = token.partition(SEPARATOR)
    if not payload or not signature:
        return None
    if not hmac.compare_digest(signature, _sign(payload, secret)):
        return None

    try:
        decoded = _unb64(payload).decode()
    except (ValueError, UnicodeDecodeError):
        return None

    parts = decoded.split("|", 3)
    if len(parts) != 4:
        return None
    issue_id, subscriber_token, kind, url = parts

    if kind not in CLICK_KINDS:
        return None
    if urlparse(url).scheme not in ALLOWED_SCHEMES:
        return None
    return issue_id, subscriber_token, kind, url


def tracked_url(
    *,
    base_url: str,
    issue_id: str,
    subscriber_token: str,
    kind: str,
    url: str,
    secret: str,
) -> str:
    """The redirect URL to put in the email in place of ``url``."""
    token = build_token(
        issue_id=issue_id,
        subscriber_token=subscriber_token,
        kind=kind,
        url=url,
        secret=secret,
    )
    return f"{base_url.rstrip('/')}/r/{token}"
