"""Editorial review workbench: auth boundary, decisions, and the approval gate.

This is the surface that lets a medical issue reach subscribers, so the access
control and the "cannot approve while items are pending" rule both matter.
"""
from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from oykos.db.repository import NewsletterRepository
from oykos.db.tables import Base
from oykos.models.news_item import (
    EditorialBlock,
    IssueMetrics,
    Newsletter,
    NewsletterSlot,
    ReviewStatus,
    SourceLink,
)
from oykos.models.taxonomy import Confidence, IssueStatus, Section
from oykos.web import app as web_app
from oykos.web import review

TOKEN = "test-review-token"  # noqa: S105
WEEK = "2026-W17"


def _slot(position: int, *, needs_review: bool) -> NewsletterSlot:
    return NewsletterSlot(
        position=position,
        section=Section.TOP_PRIORITY if position <= 3 else Section.CLINICAL,
        item_id=uuid4(),
        editorial=EditorialBlock(
            headline_operational=f"Titolo operativo {position}",
            why_it_matters=f"Motivo {position}.",
            what_to_do=["Controllare i lotti", "Informare i genitori"],
            summary="Dettaglio clinico e operativo.",
            confidence=Confidence.HIGH,
            review=ReviewStatus(
                needs_human_review=needs_review,
                review_status="pending" if needs_review else "approved",
                reviewer_role="medical_editor" if needs_review else None,
                review_reason="top priority" if needs_review else "",
            ),
        ),
        source_name="AIFA",
        source_url=f"https://www.aifa.gov.it/{position}",
        source_links=[SourceLink(label="AIFA", url=f"https://www.aifa.gov.it/{position}")],
    )


def _newsletter() -> Newsletter:
    slots = [_slot(i, needs_review=i <= 3) for i in range(1, 7)]
    return Newsletter(
        week=WEEK,
        slots=slots,
        subject_line="Briefing settimanale",
        preheader="Anteprima",
        tldr=["Prima riga", "Seconda riga", "Terza riga"],
        reading_time_minutes=7,
        status=IssueStatus.IN_REVIEW,
        metrics=IssueMetrics(italy_count=4, foreign_count=2),
    )


@pytest.fixture
def seeded(tmp_path) -> str:
    """Create the DB with one issue in review, and return its URL."""
    import asyncio

    db_url = f"sqlite+aiosqlite:///{tmp_path / 'review.db'}"

    async def _seed() -> None:
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await NewsletterRepository(session).save(_newsletter())
            await session.commit()
        await engine.dispose()

    asyncio.run(_seed())
    return db_url


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, seeded: str) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", seeded)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.it")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("BASE_URL", "http://testserver")
    monkeypatch.setenv("REVIEW_TOKEN", TOKEN)
    with TestClient(web_app.app) as test_client:
        yield test_client


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    response = client.post("/review/login", data={"token": TOKEN}, follow_redirects=False)
    assert response.status_code == 303
    return client


# ── Auth boundary ─────────────────────────────────────────

def test_queue_requires_sign_in(client: TestClient) -> None:
    assert client.get("/review").status_code == 401


def test_workbench_requires_sign_in(client: TestClient) -> None:
    assert client.get(f"/review/{WEEK}").status_code == 401


def test_actions_require_sign_in(client: TestClient) -> None:
    assert client.post(f"/review/{WEEK}/approve").status_code == 401
    assert client.post(f"/review/{WEEK}/send").status_code == 401


def test_wrong_token_is_rejected(client: TestClient) -> None:
    response = client.post("/review/login", data={"token": "wrong"})

    assert response.status_code == 401
    assert "non valido" in response.text.lower()


def test_a_forged_session_cookie_is_rejected(client: TestClient) -> None:
    client.cookies.set(review.SESSION_COOKIE, "9999999999.deadbeef")
    assert client.get("/review").status_code == 401


def test_expired_session_is_rejected() -> None:
    assert not review.session_is_valid("1.abc", TOKEN)


def test_session_roundtrip() -> None:
    assert review.session_is_valid(review.issue_session(TOKEN, 1), TOKEN)
    assert not review.session_is_valid(review.issue_session(TOKEN, 1), "other-secret")


def test_review_is_disabled_without_a_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Fail closed: no token configured means the surface does not exist."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'x.db'}")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("SMTP_USERNAME", "s@e.it")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.delenv("REVIEW_TOKEN", raising=False)

    with TestClient(web_app.app) as anon:
        assert anon.get("/review/login").status_code == 404
        assert anon.get("/review").status_code == 404


# ── Workbench ─────────────────────────────────────────────

def test_queue_lists_the_pending_issue(signed_in: TestClient) -> None:
    response = signed_in.get("/review")

    assert response.status_code == 200
    assert WEEK in response.text
    assert "3 da decidere" in response.text


def test_workbench_shows_items_and_review_reasons(signed_in: TestClient) -> None:
    response = signed_in.get(f"/review/{WEEK}")

    assert response.status_code == 200
    assert "Titolo operativo 1" in response.text
    assert "top priority" in response.text
    assert "Che cosa merita attenzione" in response.text


def test_workbench_404s_for_an_unknown_week(signed_in: TestClient) -> None:
    assert signed_in.get("/review/2099-W01").status_code == 404


def test_cannot_approve_while_items_are_pending(signed_in: TestClient) -> None:
    assert signed_in.post(f"/review/{WEEK}/approve").status_code == 409


def _approve_all(client: TestClient) -> None:
    page = client.get(f"/review/{WEEK}").text
    for item_id in _pending_item_ids(page):
        response = client.post(
            f"/review/{WEEK}/items/{item_id}",
            data={"decision": "approved"},
            follow_redirects=False,
        )
        assert response.status_code == 303


def _pending_item_ids(page: str) -> list[str]:
    ids: list[str] = []
    marker = f'action="/review/{WEEK}/items/'
    for chunk in page.split(marker)[1:]:
        item_id = chunk.split('"')[0]
        if item_id not in ids:
            ids.append(item_id)
    return ids


def test_approving_every_item_unlocks_the_issue(signed_in: TestClient) -> None:
    _approve_all(signed_in)

    response = signed_in.post(f"/review/{WEEK}/approve")

    assert response.status_code == 200
    assert "approvato" in response.text.lower()


def test_an_invalid_decision_is_rejected(signed_in: TestClient) -> None:
    item_id = _pending_item_ids(signed_in.get(f"/review/{WEEK}").text)[0]

    response = signed_in.post(
        f"/review/{WEEK}/items/{item_id}", data={"decision": "sabotage"},
    )

    assert response.status_code == 400


def test_editing_an_item_rewrites_the_headline(signed_in: TestClient) -> None:
    item_id = _pending_item_ids(signed_in.get(f"/review/{WEEK}").text)[0]

    signed_in.post(
        f"/review/{WEEK}/items/{item_id}",
        data={
            "decision": "edited",
            "headline": "Headline corretta dalla redazione",
            "why_it_matters": "Motivo rivisto.",
            "what_to_do": "Verificare i lotti\nAvvisare i genitori",
            "summary": "Dettaglio rivisto.",
            "notes": "Reso piu operativo",
        },
        follow_redirects=False,
    )

    assert "Headline corretta dalla redazione" in signed_in.get(f"/review/{WEEK}").text


def test_rejecting_an_item_removes_it_from_the_issue(signed_in: TestClient) -> None:
    before = _pending_item_ids(signed_in.get(f"/review/{WEEK}").text)

    signed_in.post(
        f"/review/{WEEK}/items/{before[0]}",
        data={"decision": "rejected", "notes": "Fuori scope"},
        follow_redirects=False,
    )

    page = signed_in.get(f"/review/{WEEK}").text
    assert before[0] not in page


def test_send_delivers_and_marks_the_issue_sent(
    signed_in: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: list[str] = []

    async def fake_deliver(newsletter, settings, session) -> bool:
        delivered.append(newsletter.week)
        return True

    monkeypatch.setattr("oykos.pipeline.weekly.deliver", fake_deliver)
    _approve_all(signed_in)

    response = signed_in.post(f"/review/{WEEK}/send")

    assert response.status_code == 200
    assert delivered == [WEEK]
    assert "inviato" in response.text.lower()


def test_failed_delivery_reports_an_error(
    signed_in: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_deliver(newsletter, settings, session) -> bool:
        return False

    monkeypatch.setattr("oykos.pipeline.weekly.deliver", failing_deliver)
    _approve_all(signed_in)

    response = signed_in.post(f"/review/{WEEK}/send")

    assert response.status_code == 502
    assert "non riuscito" in response.text.lower()


def test_logout_clears_the_session(signed_in: TestClient) -> None:
    signed_in.post("/review/logout", follow_redirects=False)
    assert signed_in.get("/review").status_code == 401
