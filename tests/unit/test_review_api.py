"""Tests for review API - S027."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from oykos.delivery.review_api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_newsletter_not_found(client: TestClient) -> None:
    resp = client.get("/api/newsletters/2026-W99")
    assert resp.status_code == 404


def test_submit_review(client: TestClient) -> None:
    from uuid import uuid4
    resp = client.post("/api/review", json={
        "item_id": str(uuid4()),
        "issue_id": str(uuid4()),
        "reviewer_role": "editor",
        "status": "approved",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_submit_review_invalid_status(client: TestClient) -> None:
    from uuid import uuid4
    resp = client.post("/api/review", json={
        "item_id": str(uuid4()),
        "issue_id": str(uuid4()),
        "reviewer_role": "editor",
        "status": "invalid",
    })
    assert resp.status_code == 400


def test_submit_feedback(client: TestClient) -> None:
    from uuid import uuid4
    resp = client.post("/api/feedback", json={
        "issue_id": str(uuid4()),
        "rating": 4,
        "comments": "Great newsletter!",
    })
    assert resp.status_code == 200


def test_submit_feedback_invalid_rating(client: TestClient) -> None:
    from uuid import uuid4
    resp = client.post("/api/feedback", json={
        "issue_id": str(uuid4()),
        "rating": 0,
    })
    assert resp.status_code == 400
