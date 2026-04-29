"""Core data models - NewsItem and related - S004."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    Geo,
    IssueStatus,
    Section,
    Setting,
    TaxonomyTag,
    Tier,
)


class KeyPassage(BaseModel):
    quote: str
    location: str = ""
    url: str = ""


class SourceRef(BaseModel):
    key: str
    name: str
    source_type: str
    country: str
    reliability_tier: int = Field(ge=0, le=5)


class ContentBlock(BaseModel):
    title: str
    published_at: datetime | None = None
    document_type: DocumentType = DocumentType.NEWS
    language: str = "it"
    raw_text: str = ""
    canonical_url: str
    key_passages: list[KeyPassage] = Field(default_factory=list)


class Classification(BaseModel):
    geo: Geo = Geo.IT
    taxonomy_tags: list[TaxonomyTag] = Field(default_factory=list)
    setting: Setting = Setting.TERRITORY
    pls_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    device_related: bool = False
    tests_mentioned: list[str] = Field(default_factory=list)


class Subscores(BaseModel):
    pls_relevance: int = Field(default=0, ge=0, le=5)
    clinical_impact: int = Field(default=0, ge=0, le=5)
    operational_impact: int = Field(default=0, ge=0, le=5)
    source_trust: int = Field(default=0, ge=0, le=5)
    novelty: int = Field(default=0, ge=0, le=5)
    actionability: int = Field(default=0, ge=0, le=5)
    urgency: int = Field(default=0, ge=0, le=5)


class ScoringBlock(BaseModel):
    score_total: float = Field(default=0.0, ge=0.0, le=100.0)
    subscores: Subscores = Field(default_factory=Subscores)
    penalties: list[str] = Field(default_factory=list)
    transferability: float = Field(default=1.0, ge=0.0, le=1.0)


class Citation(BaseModel):
    claim_id: str
    source_url: str
    supporting_passage_ref: str = ""


class ReviewStatus(BaseModel):
    needs_human_review: bool = True
    review_status: str = "pending"  # pending | approved | rejected
    reviewer_role: str | None = None


class EditorialBlock(BaseModel):
    headline_operational: str = ""
    why_it_matters: str = ""
    what_to_do: list[str] = Field(default_factory=list)
    summary: str = ""
    confidence: Confidence = Confidence.LOW
    citations: list[Citation] = Field(default_factory=list)
    review: ReviewStatus = Field(default_factory=ReviewStatus)


class NewsItem(BaseModel):
    item_id: UUID = Field(default_factory=uuid4)
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    source: SourceRef
    content: ContentBlock
    classification: Classification = Field(default_factory=Classification)
    scoring: ScoringBlock = Field(default_factory=ScoringBlock)
    editorial: EditorialBlock = Field(default_factory=EditorialBlock)


class NewsletterSlot(BaseModel):
    position: int = Field(ge=1, le=12)
    section: Section
    item_id: UUID
    editorial: EditorialBlock
    source_name: str = ""
    source_url: str = ""


class IssueMetrics(BaseModel):
    italy_count: int = 0
    foreign_count: int = 0
    section_counts: dict[str, int] = Field(default_factory=dict)


class Newsletter(BaseModel):
    issue_id: UUID = Field(default_factory=uuid4)
    week: str  # e.g. "2026-W17"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    slots: list[NewsletterSlot] = Field(default_factory=list)
    subject_line: str = ""
    subject_variant: str = ""
    html_content: str = ""
    text_content: str = ""
    status: IssueStatus = IssueStatus.DRAFT
    metrics: IssueMetrics = Field(default_factory=IssueMetrics)


class ReviewDecision(BaseModel):
    decision_id: UUID = Field(default_factory=uuid4)
    item_id: UUID
    issue_id: UUID
    reviewer_role: str
    status: str  # approved | rejected | edited
    edits: dict[str, str] | None = None
    notes: str | None = None
    decided_at: datetime = Field(default_factory=datetime.utcnow)
