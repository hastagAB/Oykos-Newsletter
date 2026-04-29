"""SQLAlchemy ORM tables - S005."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class NewsItemRow(Base):
    __tablename__ = "news_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source_key: Mapped[str] = mapped_column(String(100), index=True)
    source_name: Mapped[str] = mapped_column(String(255))
    source_country: Mapped[str] = mapped_column(String(10))
    source_reliability: Mapped[int] = mapped_column(Integer)

    # Content
    title: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), default="news")
    language: Mapped[str] = mapped_column(String(10), default="it")
    raw_text: Mapped[str] = mapped_column(Text, default="")

    # Classification
    geo: Mapped[str] = mapped_column(String(10), default="IT")
    taxonomy_tags: Mapped[dict] = mapped_column(JSON, default=list)
    setting: Mapped[str] = mapped_column(String(20), default="territory")
    pls_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    device_related: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scoring
    score_total: Mapped[float] = mapped_column(Float, default=0.0)
    subscores: Mapped[dict] = mapped_column(JSON, default=dict)
    penalties: Mapped[dict] = mapped_column(JSON, default=list)
    transferability: Mapped[float] = mapped_column(Float, default=1.0)

    # Editorial
    headline_operational: Mapped[str] = mapped_column(Text, default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    what_to_do: Mapped[dict] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(10), default="low")
    citations: Mapped[dict] = mapped_column(JSON, default=list)
    key_passages: Mapped[dict] = mapped_column(JSON, default=list)

    # Review
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewer_role: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


class NewsletterRow(Base):
    __tablename__ = "newsletters"

    issue_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    week: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    subject_line: Mapped[str] = mapped_column(Text, default="")
    subject_variant: Mapped[str] = mapped_column(Text, default="")
    html_content: Mapped[str] = mapped_column(Text, default="")
    text_content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    slots: Mapped[dict] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class ReviewDecisionRow(Base):
    __tablename__ = "review_decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    issue_id: Mapped[str] = mapped_column(String(36), index=True)
    reviewer_role: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    edits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SubscriberRow(Base):
    """Subscriber with GDPR-compliant double opt-in."""
    __tablename__ = "subscribers"

    subscriber_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    # Status: pending_confirmation -> active -> unsubscribed
    status: Mapped[str] = mapped_column(String(30), default="pending_confirmation", index=True)
    confirm_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    unsubscribe_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # GDPR consent record
    consented_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Referral tracking
    referral_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    referred_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    # A/B group: "A" or "B"
    ab_group: Mapped[str] = mapped_column(String(1), default="A")


class FeedbackRow(Base):
    """Per-issue reader feedback (micro-survey)."""
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issue_id: Mapped[str] = mapped_column(String(36), index=True)
    subscriber_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
