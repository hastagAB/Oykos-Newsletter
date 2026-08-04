"""Public subscriber surface: double opt-in, preferences, feedback, archive.

The security-critical property here is that the confirmation token only ever
reaches the inbox of the address being subscribed.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from oykos.web import app as web_app
from oykos.web import public


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    async def fake_send(**kwargs) -> bool:
        captured.append(kwargs)
        return True

    monkeypatch.setattr(public, "send_newsletter", fake_send)
    return captured


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'web.db'}")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.it")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("BASE_URL", "https://oykos.example.it")
    monkeypatch.delenv("REVIEW_TOKEN", raising=False)
    with TestClient(web_app.app) as test_client:
        yield test_client


def _subscribe(client: TestClient, email: str = "pls@example.it") -> dict:
    response = client.post("/api/subscribe", json={"email": email})
    assert response.status_code == 200
    return response.json()


def _confirm_token(sent_emails: list[dict]) -> str:
    return sent_emails[0]["text_content"].split("/confirm/")[1].split("\n")[0]


# ── Double opt-in ─────────────────────────────────────────

def test_confirmation_token_never_appears_in_the_response(client, sent_emails) -> None:
    body = _subscribe(client)

    assert "confirm_url" not in body
    assert "token" not in str(body).lower()


def test_confirmation_link_is_emailed_to_the_subscriber(client, sent_emails) -> None:
    _subscribe(client)

    assert sent_emails[0]["to_emails"] == ["pls@example.it"]
    assert "/confirm/" in sent_emails[0]["text_content"]


def test_resubscribing_does_not_disclose_an_existing_subscription(client, sent_emails) -> None:
    assert _subscribe(client) == _subscribe(client)
    assert len(sent_emails) == 1


def test_confirming_activates_the_subscriber(client, sent_emails) -> None:
    _subscribe(client)

    response = client.get(f"/confirm/{_confirm_token(sent_emails)}")

    assert response.status_code == 200
    assert "confermata" in response.text.lower()


def test_a_forged_confirmation_token_is_rejected(client) -> None:
    assert client.get("/confirm/forged").status_code == 400


def test_a_forged_unsubscribe_token_is_rejected(client) -> None:
    assert client.post("/unsubscribe/forged").status_code == 400


def test_invalid_email_is_rejected(client, sent_emails) -> None:
    assert client.post("/api/subscribe", json={"email": "nope"}).status_code == 422
    assert sent_emails == []


def test_html_signup_form_works_without_javascript(client, sent_emails) -> None:
    response = client.post("/subscribe", data={"email": "form@example.it", "name": "Dr"})

    assert response.status_code == 200
    assert len(sent_emails) == 1


# ── Preferences ───────────────────────────────────────────

def _activate(client: TestClient, sent_emails: list[dict]) -> str:
    """Subscribe, confirm, and return the subscriber's preferences token."""
    _subscribe(client)
    confirm = client.get(f"/confirm/{_confirm_token(sent_emails)}")
    return confirm.text.split("/preferences/")[1].split('"')[0]


def test_preferences_page_renders_for_a_valid_token(client, sent_emails) -> None:
    token = _activate(client, sent_emails)

    response = client.get(f"/preferences/{token}")

    assert response.status_code == 200
    assert "Clinica del territorio" in response.text


def test_preferences_are_saved(client, sent_emails) -> None:
    token = _activate(client, sent_emails)

    response = client.post(
        f"/preferences/{token}",
        data={"topics": ["clinica", "farmaci"], "alert_opt_in": "1", "region": "Veneto"},
    )

    assert "Preferenze salvate" in response.text
    assert "Veneto" in client.get(f"/preferences/{token}").text


def test_unknown_topics_are_ignored(client, sent_emails) -> None:
    token = _activate(client, sent_emails)

    response = client.post(
        f"/preferences/{token}", data={"topics": ["clinica", "hacker"], "alert_opt_in": ""},
    )

    assert response.status_code == 200


def test_preferences_reject_an_unknown_token(client) -> None:
    assert client.get("/preferences/nope").status_code == 404


def test_generic_preferences_link_explains_itself(client) -> None:
    """The newsletter footer carries a tokenless link; it must not 404."""
    response = client.get("/preferences")

    assert response.status_code == 200
    assert "link personale" in response.text.lower()


# ── Feedback ──────────────────────────────────────────────

def test_structured_feedback_is_accepted(client) -> None:
    response = client.post(
        "/feedback/abc",
        data={"rating": "4", "too_long": "1", "comment": "Utile ma lungo"},
    )

    assert response.status_code == 200
    assert "Grazie" in response.text


def test_feedback_api_rejects_an_out_of_range_rating(client) -> None:
    assert client.post("/api/feedback", json={"issue_id": "a", "rating": 9}).status_code == 422


def test_feedback_form_rejects_an_out_of_range_rating(client) -> None:
    assert client.post("/feedback/abc", data={"rating": "9"}).status_code == 400


# ── Archive and GDPR ──────────────────────────────────────

def test_archive_lists_published_issues(client) -> None:
    response = client.get("/archive")

    assert response.status_code == 200
    assert "Nessuna edizione pubblicata finora" in response.text


def test_archive_issue_not_found(client) -> None:
    assert client.get("/archive/2026-W17").status_code == 404


def test_gdpr_erasure(client, sent_emails) -> None:
    _subscribe(client)

    assert client.post("/api/erase", json={"email": "pls@example.it"}).status_code == 200
    assert client.post("/api/erase", json={"email": "ghost@example.it"}).status_code == 404


def test_landing_page_renders(client) -> None:
    assert client.get("/").status_code == 200
