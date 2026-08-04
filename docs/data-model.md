# Data Model Reference

All models use Pydantic v2 with strict validation. This document is the canonical
reference - code in `src/oykos/models/` must match. Changes require an ADR; see
`.vibe/decisions/ADR-001-blueprint-conformance.md`.

Datetimes are timezone-aware (`datetime.now(UTC)`) in the domain model. The
database layer normalises them to naive UTC on write so SQLite and PostgreSQL
behave identically for range comparisons.

---

## Source

```python
class Source:
    key: str                    # e.g. "aifa_safety"
    name: str                   # "AIFA Safety Communications"
    url: str                    # Primary feed/page URL
    source_type: SourceType     # rss | scrape | api | pdf
    tier: Tier                  # tier_1_italy | tier_2_europe | tier_3_global | radar
    reliability: int            # 0-5, see docs/scoring.md
    country: str                # "IT", "EU", "US", etc.
    category_hints: list[TaxonomyTag]  # Expected content categories
    enabled: bool               # Toggle without removal
    fetch_config: FetchConfig   # timeout, max_items, headers, scrape selectors
```

`Tier.RADAR` is a **source** tier for low-trust outlets. It is not a newsletter
section: `Section` has no `RADAR` member, and low-trust items are excluded by
the gates rather than routed anywhere.

`SourceType.PDF` exists in the enum but no registry entry uses it; there is no
PDF connector.

## NewsItem (Core Entity)

```python
class NewsItem:
    item_id: UUID
    ingested_at: datetime
    source: SourceRef           # key, name, source_type, country, reliability_tier
    content: ContentBlock       # title, published_at, doc_type, language, raw_text, key_passages
    classification: Classification  # geo, taxonomy_tags, setting, pls_relevance, device_related
    scoring: ScoringBlock       # score_total, subscores (7 dims + transferability), penalties
    editorial: EditorialBlock   # headline, why_matters, what_to_do, summary, confidence, citations, review
    gating: Gating              # outcome of the 3 selection gates
```

### ContentBlock
```python
class ContentBlock:
    title: str
    published_at: datetime | None
    document_type: DocumentType  # safety_communication | guideline | consensus | surveillance_report | legal_update | event | news | study
    language: str               # ISO 639-1
    raw_text: str
    canonical_url: str
    key_passages: list[KeyPassage]  # quote, location, url
```

### Classification
```python
class Classification:
    geo: Geo                    # IT | EU | GLOBAL
    taxonomy_tags: list[TaxonomyTag]
    setting: Setting            # territory | hospital | mixed
    pls_relevance: float        # 0.0-1.0
    device_related: bool
    tests_mentioned: list[str]
```

### ScoringBlock
```python
class ScoringBlock:
    score_total: float          # 0-100
    subscores: Subscores
    penalties: list[str]        # "duplicate", "paywall", "press_release", "single_source"

    @property
    def transferability(self) -> float:   # delegates to subscores
        ...

class Subscores:
    pls_relevance: int          # 0-5
    clinical_impact: int        # 0-5
    operational_impact: int     # 0-5
    source_trust: int           # 0-5
    novelty: int                # 0-5
    actionability: int          # 0-5
    urgency: int                # 0-5
    transferability: float      # 0.65-0.95 for foreign items, 1.0 for Italian
```

The blueprint item schema places `transferability` inside `subscores`, so that is
its canonical home. `ScoringBlock.transferability` is a read-only property, which
keeps the scoring engine the single writer.

### Gating
```python
class Gating:
    passed: bool                # cleared all 3 selection gates
    exclusions: list[ExclusionReason]
```

An item that fails any gate is excluded. There is no `radar_only` demotion path.

### EditorialBlock
```python
class EditorialBlock:
    headline_operational: str   # max 90 chars
    why_it_matters: str         # 1 sentence
    what_to_do: list[str]       # 2-4 bullet actions
    summary: str                # 3-6 lines of clinical/operational detail
    confidence: Confidence      # high | medium | low
    citations: list[Citation]   # claim_id, source_url, supporting_passage_ref
    review: ReviewStatus        # needs_human_review, review_status, reviewer_role, review_reason
    unsupported_claims: list[str]  # set by verification
    blocked: bool               # verification refused this item
```

`ReviewStatus.needs_human_review` defaults to `True` and the composer sets it on
every selected item. There is no sampling policy and no `DecisionCard` - see
[deviations.md](deviations.md).

---

## Newsletter

```python
class Newsletter:
    issue_id: UUID
    week: str                   # "2026-W17"
    created_at: datetime
    slots: list[NewsletterSlot]  # Ordered, max 12
    subject_line: str
    preheader: str              # inbox preview text
    tldr: list[str]             # "what is really changing this week", 3 lines
    reading_time_minutes: int   # clamped to 6-8
    html_content: str
    text_content: str
    public_url: str             # WordPress post URL, empty if not published
    status: IssueStatus         # draft | in_review | approved | sent
    metrics: IssueMetrics       # italy_count, foreign_count, section_counts

class NewsletterSlot:
    position: int               # 1-12
    section: Section            # top_priority | clinical | regulatory | device | cme
    item_id: UUID
    editorial: EditorialBlock
    source_name: str
    source_url: str
    source_links: list[SourceLink]      # 2-3 links, label + url
```

`public_url` is written by `oykos.delivery.wordpress.publish_issue` before the
email is rendered, which is what drives the "Leggi online" link. It stays empty
when WordPress publishing is disabled or fails. There is no `subject_variant`:
subject line A/B testing was cut.

## ReviewDecision

```python
class ReviewDecision:
    decision_id: UUID
    item_id: UUID
    issue_id: UUID
    reviewer_role: str          # medical_editor | legal_editor
    status: str                 # approved | rejected | edited
    edits: dict | None          # Fields that were changed
    notes: str | None
    decided_at: datetime
```

---

## Enums

```python
class Tier(str, Enum):
    TIER_1_ITALY = "tier_1_italy"
    TIER_2_EUROPE = "tier_2_europe"
    TIER_3_GLOBAL = "tier_3_global"
    RADAR = "radar"

class Geo(str, Enum):
    IT = "IT"
    EU = "EU"
    GLOBAL = "GLOBAL"

class Setting(str, Enum):
    TERRITORY = "territory"
    HOSPITAL = "hospital"
    MIXED = "mixed"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class DocumentType(str, Enum):
    SAFETY_COMMUNICATION = "safety_communication"
    GUIDELINE = "guideline"
    CONSENSUS = "consensus"
    SURVEILLANCE_REPORT = "surveillance_report"
    LEGAL_UPDATE = "legal_update"
    EVENT = "event"
    NEWS = "news"
    STUDY = "study"

class Section(str, Enum):
    TOP_PRIORITY = "top_priority"
    CLINICAL = "clinical"
    REGULATORY = "regulatory"
    DEVICE = "device"
    CME = "cme"

class SourceType(str, Enum):
    RSS = "rss"
    SCRAPE = "scrape"
    API = "api"
    PDF = "pdf"          # declared, unused - no PDF connector

class IssueStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SENT = "sent"

class Penalty(str, Enum):
    DUPLICATE = "duplicate"
    PAYWALL = "paywall"
    PRESS_RELEASE = "press_release"
    SINGLE_SOURCE = "single_source"

class ExclusionReason(str, Enum):
    NO_PLS_RELEVANCE = "no_pls_relevance"
    UNRELIABLE_SOURCE = "unreliable_source"
    NOT_ACTIONABLE = "not_actionable"
    GENERALIST_NEWS = "generalist_news"
    PREPRINT = "preprint"
    VENDOR_MARKETING = "vendor_marketing"

class ReviewerRole(str, Enum):
    MEDICAL_EDITOR = "medical_editor"
    LEGAL_EDITOR = "legal_editor"

class TaxonomyTag(str, Enum):
    # Clinic Territory
    RESPIRATORY = "respiratory"
    GASTROENTERITIS = "gastroenteritis"
    DERMATOLOGY = "dermatology"
    ALLERGOLOGY = "allergology"
    NEURO_DEVELOPMENT = "neuro_development"
    EMERGENCIES_TRIAGE = "emergencies_triage"
    # Prevention & Public Health
    VACCINATIONS = "vaccinations"
    SURVEILLANCE = "surveillance"
    ANTIBIOTIC_RESISTANCE = "antibiotic_resistance"
    # Medications
    DRUG_SAFETY = "drug_safety"
    DRUG_AUTHORIZATION = "drug_authorization"
    DRUG_SHORTAGE = "drug_shortage"
    # Studio & Compliance
    ACN_AGREEMENTS = "acn_agreements"
    PRIVACY = "privacy"
    TELEMEDICINE = "telemedicine"
    # Diagnostics & POCT
    RAPID_TESTS = "rapid_tests"
    POCT_LAB = "poct_lab"
    FUNCTIONAL_DIAGNOSTICS = "functional_diagnostics"
    SCREENING = "screening"
    DEVICE_SAFETY = "device_safety"
    # Training
    CME_TRAINING = "cme_training"
    CONGRESSES = "congresses"
    # Research and AI in pediatric practice
    RESEARCH_EVIDENCE = "research_evidence"
    AI_DIGITAL_HEALTH = "ai_digital_health"
```

`RESEARCH_EVIDENCE` and `AI_DIGITAL_HEALTH` back the Nature Medicine, npj
Digital Medicine and Lancet Digital Health sources. `AI_DIGITAL_HEALTH` also
routes an item to the Device/Test section (`ranker.DEVICE_TAGS`).

---

## Persistence notes

The ORM tables in `src/oykos/db/tables.py` flatten these models into columns.
Fields that no longer exist anywhere in the stack: `embedding` on `news_items`,
`subject_variant` on `newsletters`, and `ab_group` / `referral_code` /
`referred_by` / `referral_count` on `subscribers`. See
[deviations.md](deviations.md).
