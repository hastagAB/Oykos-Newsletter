"""SQLAlchemy ORM tables - S005."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Naive UTC. The database layer stores UTC without an offset so that
    SQLite and PostgreSQL behave identically for range comparisons."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class NewsItemRow(Base):
    __tablename__ = "news_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
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
    access_limited: Mapped[bool] = mapped_column(Boolean, default=False)

    # Classification
    geo: Mapped[str] = mapped_column(String(10), default="IT")
    taxonomy_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    setting: Mapped[str] = mapped_column(String(20), default="territory")
    pls_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    device_related: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scoring
    score_total: Mapped[float] = mapped_column(Float, default=0.0)
    subscores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    penalties: Mapped[list[str]] = mapped_column(JSON, default=list)
    transferability: Mapped[float] = mapped_column(Float, default=1.0)

    # Editorial
    source_note: Mapped[str] = mapped_column(Text, default="")
    headline_operational: Mapped[str] = mapped_column(Text, default="")
    what_emerges: Mapped[str] = mapped_column(Text, default="", server_default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    what_to_do: Mapped[list[str]] = mapped_column(JSON, default=list)
    implication_kind: Mapped[str] = mapped_column(
        String(30), default="worth_attention", server_default="worth_attention",
    )
    rules_version: Mapped[str] = mapped_column(String(20), default="", server_default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(10), default="low")
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    key_passages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Review
    needs_human_review: Mapped[bool] = mapped_column(Boolean, default=True)
    review_status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewer_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_reason: Mapped[str] = mapped_column(String(80), default="")

    # Gating (3 selection gates)
    gate_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    exclusions: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Editorial verification
    unsupported_claims: Mapped[list[str]] = mapped_column(JSON, default=list)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)


class AlertRow(Base):
    """Ledger of trigger alerts, used to enforce the monthly cap."""

    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    category: Mapped[str] = mapped_column(String(40))
    level: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(Text, default="")
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class NewsletterRow(Base):
    __tablename__ = "newsletters"

    issue_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    week: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    subject_line: Mapped[str] = mapped_column(Text, default="")
    preheader: Mapped[str] = mapped_column(Text, default="")
    # Which single element was varied this week, and the B text for it.
    ab_element: Mapped[str] = mapped_column(String(20), default="none")
    ab_variant_b: Mapped[str] = mapped_column(Text, default="")
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    tldr: Mapped[list[str]] = mapped_column(JSON, default=list)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    html_content: Mapped[str] = mapped_column(Text, default="")
    text_content: Mapped[str] = mapped_column(Text, default="")
    public_url: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    slots: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Review workflow
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReviewDecisionRow(Base):
    __tablename__ = "review_decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    item_id: Mapped[str] = mapped_column(String(36), index=True)
    issue_id: Mapped[str] = mapped_column(String(36), index=True)
    reviewer_role: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    edits: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    # Preferences: empty topic list means "everything"
    topics: Mapped[list[str]] = mapped_column(JSON, default=list)
    alert_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    region: Mapped[str] = mapped_column(String(40), default="")
    # Stable A/B bucket, assigned once so a subscriber never flips between
    # variants and week-on-week comparisons stay homogeneous.
    ab_group: Mapped[str] = mapped_column(String(1), default="A", index=True)


class ClickEventRow(Base):
    """One recorded click.

    Personal data: it links a subscriber to what they chose to read.
    ``SubscriberRepository.delete_subscriber_data`` deletes these rows on erasure,
    and the privacy notice must mention click measurement before it is enabled.
    """
    __tablename__ = "click_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issue_id: Mapped[str] = mapped_column(String(36), index=True)
    subscriber_id: Mapped[str] = mapped_column(String(36), index=True)
    week: Mapped[str] = mapped_column(String(10), index=True)
    # "source" (a link out to a primary source) or "cta".
    kind: Mapped[str] = mapped_column(String(20), default="source", index=True)
    target_url: Mapped[str] = mapped_column(Text, default="")
    ab_group: Mapped[str] = mapped_column(String(1), default="A")
    clicked_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ResolvedEventSourceRow(Base):
    """Where a registry row's real event listing was found, and when verified.

    Discovery is expensive and mostly stable, so the resolved URL is cached and
    re-verified rather than rediscovered every week.
    """
    __tablename__ = "event_sources_resolved"

    source_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    listing_url: Mapped[str] = mapped_column(Text, default="")
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    needs_manual_review: Mapped[bool] = mapped_column(Boolean, default=False)


class EventRow(Base):
    """A crawled event. Selection uses the event date, never these timestamps."""
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(Text)
    promoter: Mapped[str] = mapped_column(String(255), default="")
    organiser: Mapped[str] = mapped_column(String(255), default="")
    detail_url: Mapped[str] = mapped_column(Text)
    programme_url: Mapped[str] = mapped_column(Text, default="")
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)

    start_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    venue: Mapped[str] = mapped_column(String(255), default="")
    event_format: Mapped[str] = mapped_column(String(20), default="unknown")

    stated_audience: Mapped[str] = mapped_column(Text, default="")
    programme_evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    pls_fit: Mapped[str] = mapped_column(String(20), default="unsupported", index=True)

    ecm_accredited: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ecm_credits: Mapped[str] = mapped_column(String(60), default="")
    accredited_professions: Mapped[list[str]] = mapped_column(JSON, default=list)
    registration_status: Mapped[str] = mapped_column(String(120), default="")
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    early_registration_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fee: Mapped[str] = mapped_column(String(120), default="")

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    why_relevant: Mapped[str] = mapped_column(Text, default="")
    is_national_pls_congress: Mapped[bool] = mapped_column(Boolean, default=False)
    dedup_key: Mapped[str] = mapped_column(String(400), index=True, default="")


class FeedbackRow(Base):
    """Per-issue reader feedback (micro-survey)."""
    __tablename__ = "feedback"

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    issue_id: Mapped[str] = mapped_column(String(36), index=True)
    subscriber_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1-5
    comment: Mapped[str] = mapped_column(Text, default="")
    # Structured signals the blueprint asks for, beyond the star rating.
    too_long: Mapped[bool] = mapped_column(Boolean, default=False)
    too_many_devices: Mapped[bool] = mapped_column(Boolean, default=False)
    not_relevant: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
