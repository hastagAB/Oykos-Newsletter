"""WordPress publishing: the post payload and the "Leggi online" link it returns.

The email carries whatever URL this module hands back, so a silent failure must
degrade to an empty string rather than a broken link.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from oykos.config import Settings
from oykos.delivery import wordpress
from oykos.delivery.wordpress import build_post_payload, publish_issue
from oykos.models.news_item import Newsletter

WEEK = "2026-W17"


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "openai_api_key": "sk-test",
        "wordpress_url": "https://oykomed.it/",
        "wordpress_user": "editor",
        "wordpress_app_password": "abcd efgh ijkl",
        "wordpress_category_id": 7,
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _newsletter(**overrides: object) -> Newsletter:
    base: dict[str, Any] = {
        "week": WEEK,
        "subject_line": "Briefing settimanale",
        "preheader": "Anteprima della settimana",
        "html_content": "<p>Contenuto</p>",
    }
    base.update(overrides)
    return Newsletter(**base)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.text = "body"
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    """Records the single POST the publisher makes, and answers with canned data."""

    def __init__(self, response: _FakeResponse, calls: list[dict[str, Any]]) -> None:
        self._response = response
        self._calls = calls

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        self._calls.append({"url": url, **kwargs})
        return self._response


def _patch_client(
    monkeypatch: pytest.MonkeyPatch, response: _FakeResponse,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        wordpress.httpx,
        "AsyncClient",
        lambda **_kwargs: _FakeAsyncClient(response, calls),
    )
    return calls


# ── Payload ───────────────────────────────────────────────

def test_payload_carries_the_subject_slug_status_and_category() -> None:
    payload = build_post_payload(_settings(wordpress_status="draft"), _newsletter())

    assert payload["title"] == "Briefing settimanale"
    assert payload["slug"] == "briefing-2026-w17"
    assert payload["status"] == "draft"
    assert payload["categories"] == [7]
    assert payload["content"] == "<p>Contenuto</p>"
    assert payload["excerpt"] == "Anteprima della settimana"


def test_payload_falls_back_to_the_issue_title_without_a_subject_line() -> None:
    settings = _settings()
    payload = build_post_payload(settings, _newsletter(subject_line=""))

    assert payload["title"] == f"{settings.newsletter_title} - {WEEK}"


def test_payload_omits_the_category_when_none_is_configured() -> None:
    payload = build_post_payload(_settings(wordpress_category_id=0), _newsletter())

    assert "categories" not in payload


# ── Publishing ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_publish_returns_the_link_from_a_created_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    link = "https://oykomed.it/briefing-2026-w17"
    calls = _patch_client(monkeypatch, _FakeResponse(201, {"link": link}))

    assert await publish_issue(_settings(), _newsletter()) == link
    assert calls[0]["url"] == "https://oykomed.it/wp-json/wp/v2/posts"
    assert calls[0]["json"]["slug"] == "briefing-2026-w17"
    assert calls[0]["headers"]["Authorization"].startswith("Basic ")


@pytest.mark.asyncio
async def test_publish_returns_empty_string_when_wordpress_rejects_the_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _FakeResponse(403, {"link": "https://oykomed.it/nope"}))

    assert await publish_issue(_settings(), _newsletter()) == ""


@pytest.mark.asyncio
async def test_publish_is_skipped_when_wordpress_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_client(monkeypatch, _FakeResponse(201, {"link": "https://oykomed.it/x"}))

    assert await publish_issue(_settings(wordpress_url=""), _newsletter()) == ""
    assert calls == []


@pytest.mark.asyncio
async def test_a_transport_failure_does_not_break_the_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingClient(_FakeAsyncClient):
        async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            raise httpx.ConnectTimeout("no route")

    monkeypatch.setattr(
        wordpress.httpx,
        "AsyncClient",
        lambda **_kwargs: _FailingClient(_FakeResponse(201), []),
    )

    assert await publish_issue(_settings(), _newsletter()) == ""
