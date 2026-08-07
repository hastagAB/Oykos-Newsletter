"""Event model - the minimum record required before editorial ranking.

The hard data quality rule from the editorial feedback: an event without a
verified start date or official detail URL must not be published automatically,
and ECM credits, deadlines, accredited professions and audience are never
inferred. Every field here is either extracted from the page or left empty.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventFormat(str, Enum):
    ONSITE = "onsite"
    ONLINE = "online"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class PLSFit(str, Enum):
    """How the PLS audience was established, not how relevant it feels."""

    EXPLICIT = "explicit"
    PROGRAMME = "programme"
    UNSUPPORTED = "unsupported"


class Event(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)

    source_id: str = ""
    title: str
    promoter: str = ""
    organiser: str = ""
    detail_url: str
    programme_url: str = ""
    source_urls: list[str] = Field(default_factory=list)

    start_date: date
    end_date: date | None = None
    city: str = ""
    region: str = ""
    venue: str = ""
    event_format: EventFormat = EventFormat.UNKNOWN

    # Copied from the page, never paraphrased: this is the evidence for the
    # audience filter and an editor must be able to check it.
    stated_audience: str = ""
    programme_evidence: list[str] = Field(default_factory=list)
    pls_fit: PLSFit = PLSFit.UNSUPPORTED

    ecm_accredited: bool | None = None
    ecm_credits: str = ""
    accredited_professions: list[str] = Field(default_factory=list)
    registration_status: str = ""
    registration_deadline: date | None = None
    early_registration_deadline: date | None = None
    fee: str = ""

    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    relevance_score: float = Field(default=0.0, ge=0.0, le=100.0)
    why_relevant: str = ""
    is_national_pls_congress: bool = False
    needs_human_review: bool = True

    @property
    def is_publishable(self) -> bool:
        """Whether this record may be published without a human filling gaps."""
        return bool(
            self.title
            and self.detail_url.startswith("http")
            and self.pls_fit is not PLSFit.UNSUPPORTED,
        )

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """Normalised title, start date and city - the merge key."""
        title = " ".join(self.title.lower().split())
        return (title, self.start_date.isoformat(), self.city.strip().lower())
