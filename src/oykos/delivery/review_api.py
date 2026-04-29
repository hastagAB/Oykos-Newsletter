"""FastAPI review interface - S027."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from oykos.models.news_item import ReviewDecision
from oykos.models.taxonomy import IssueStatus

logger = logging.getLogger(__name__)

app = FastAPI(title="Oykos Newsletter Review", version="0.1.0")


# In-memory store for simplicity; real impl uses repository
_newsletters: dict[str, dict] = {}
_decisions: list[ReviewDecision] = []


class ReviewRequest(BaseModel):
    item_id: str
    issue_id: str
    reviewer_role: str
    status: str  # approved | rejected | edited
    edits: dict[str, str] | None = None
    notes: str | None = None


class FeedbackRequest(BaseModel):
    issue_id: str
    rating: int  # 1-5
    comments: str = ""


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/newsletters/{week}")
async def get_newsletter(week: str):
    """Get newsletter by week identifier."""
    if week not in _newsletters:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    return _newsletters[week]


@app.post("/api/review")
async def submit_review(req: ReviewRequest):
    """Submit a review decision for a newsletter item."""
    if req.status not in ("approved", "rejected", "edited"):
        raise HTTPException(status_code=400, detail="Invalid status")

    decision = ReviewDecision(
        item_id=UUID(req.item_id),
        issue_id=UUID(req.issue_id),
        reviewer_role=req.reviewer_role,
        status=req.status,
        edits=req.edits,
        notes=req.notes,
    )
    _decisions.append(decision)
    logger.info("Review submitted: %s -> %s", req.item_id, req.status)
    return {"status": "accepted", "decision_id": str(decision.decision_id)}


@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Endpoint for reader feedback (RFC per design doc)."""
    if not 1 <= req.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")
    logger.info("Feedback for %s: rating=%d", req.issue_id, req.rating)
    return {"status": "received"}


@app.post("/api/newsletters/{week}/approve")
async def approve_newsletter(week: str):
    """Approve a newsletter for sending."""
    if week not in _newsletters:
        raise HTTPException(status_code=404, detail="Newsletter not found")
    _newsletters[week]["status"] = IssueStatus.APPROVED.value
    return {"status": "approved", "week": week}
