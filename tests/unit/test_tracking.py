"""Click tracking: signing, and the measurement indicators.

Guidelines section 11 asks for unique clicks, source clicks, return in the
following weeks and unsubscribes, compared across variants that differ in
exactly one element.
"""
from __future__ import annotations

import pytest

from oykos.delivery.tracking import build_token, parse_token, tracked_url

SECRET = "test-tracking-secret"
ISSUE = "11111111-1111-1111-1111-111111111111"
TOKEN = "subscriber-unsubscribe-token"
TARGET = "https://sip.it/2026/08/03/linee-guida"


def _token(**overrides: str) -> str:
    payload = {
        "issue_id": ISSUE,
        "subscriber_token": TOKEN,
        "kind": "source",
        "url": TARGET,
        "secret": SECRET,
    }
    payload.update(overrides)
    return build_token(**payload)  # type: ignore[arg-type]


def test_round_trip() -> None:
    assert parse_token(_token(), SECRET) == (ISSUE, TOKEN, "source", TARGET)


def test_a_token_signed_with_another_secret_is_refused() -> None:
    assert parse_token(_token(secret="attacker"), SECRET) is None


def test_tampering_with_the_destination_is_refused() -> None:
    """Without this the endpoint is an open redirect wearing our domain."""
    good = _token()
    payload, _, signature = good.partition(".")
    forged = build_token(
        issue_id=ISSUE,
        subscriber_token=TOKEN,
        kind="source",
        url="https://phishing.example/login",
        secret="attacker",
    )
    forged_payload = forged.partition(".")[0]

    assert parse_token(f"{forged_payload}.{signature}", SECRET) is None
    assert parse_token(f"{payload}.{signature}", SECRET) is not None


@pytest.mark.parametrize(
    "token",
    ["", ".", "garbage", "no-separator", "YWJj.YWJj"],
)
def test_malformed_tokens_are_refused(token: str) -> None:
    assert parse_token(token, SECRET) is None


@pytest.mark.parametrize("scheme", ["javascript:alert(1)", "file:///etc/passwd", "ftp://x.it"])
def test_non_http_destinations_are_refused(scheme: str) -> None:
    """A signed token must still not be able to carry a dangerous scheme."""
    token = build_token(
        issue_id=ISSUE,
        subscriber_token=TOKEN,
        kind="source",
        url=scheme,
        secret=SECRET,
    )
    assert parse_token(token, SECRET) is None


def test_unknown_click_kind_is_refused() -> None:
    token = build_token(
        issue_id=ISSUE,
        subscriber_token=TOKEN,
        kind="pixel",
        url=TARGET,
        secret=SECRET,
    )
    assert parse_token(token, SECRET) is None


def test_tracked_url_points_at_our_own_redirect() -> None:
    url = tracked_url(
        base_url="https://oykos-newsletter.fly.dev/",
        issue_id=ISSUE,
        subscriber_token=TOKEN,
        kind="cta",
        url=TARGET,
        secret=SECRET,
    )

    assert url.startswith("https://oykos-newsletter.fly.dev/r/")
    assert TARGET not in url  # the destination is opaque, not a query parameter
