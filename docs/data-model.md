# Data Model Reference

All models use Pydantic v2 with strict validation. This document is the canonical reference - code in `src/oykos/models/` must match.

---

## Source

```python
class Source:
    key: str                    # e.g. "aifa_safety"
    name: str                   # "AIFA Safety Communications"
    url: str                    # Primary feed/page URL
    source_type: SourceType     # rss | scrape | api | pdf
    tier: Tier                  # tier_1_italy | tier_2_europe | tier_3_global | radar
    reliability: ReliabilityLevel  # institutional | society | journal | secondary
    country: str                # "IT", "EU", "US", etc.
    category_hints: list[TaxonomyTag]  # Expected content categories
    enabled: bool               # Toggle without removal
    fetch_config: FetchConfig   # Timeout, max_items, custom headers
```

## NewsItem (Core Entity)

```python
class NewsItem:
    item_id: UUID
    ingested_at: datetime
    source: SourceRef           # key, name, type, country, reliability_tier
    content: ContentBlock       # title, published_at, doc_type, language, raw_text, key_passages
    classification: Classification  # geo, taxonomy_tags, setting, pls_relevance, device_related
    scoring: ScoringBlock       # score_total, subscores (7 dims), penalties
    editorial: EditorialBlock   # headline, why_matters, what_to_do, summary, confidence, citations, review
```

### ContentBlock
```python
class ContentBlock:
    title: str
    published_at: datetime | None
    document_type: DocumentType  # safety_communication | guideline | consensus | surveillance_report | legal_update | event
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
    penalties: list[str]        # "paywall", "single_source", "duplicate"
    transferability: float      # 0.6-1.0 (1.0 for Italian items)

class Subscores:
    pls_relevance: int          # 0-5
    clinical_impact: int        # 0-5
    operational_impact: int     # 0-5
    source_trust: int           # 0-5
    novelty: int                # 0-5
    actionability: int          # 0-5
    urgency: int                # 0-5
```

### EditorialBlock
```python
class EditorialBlock:
    headline_operational: str   # max 90 chars
    why_it_matters: str         # 1 sentence
    what_to_do: list[str]       # 2-4 bullet actions
    summary: str                # 3-6 lines
    confidence: Confidence      # high | medium | low
    citations: list[Citation]   # claim_id, source_url, supporting_passage_ref
    review: ReviewStatus        # needs_human_review, review_status, reviewer_role
```

---

## Newsletter

```python
class Newsletter:
    issue_id: UUID
    week: str                   # "2026-W17"
    created_at: datetime
    slots: list[NewsletterSlot]  # Ordered, max 12
    subject_line: str
    subject_variant: str        # A/B
    html_content: str
    text_content: str
    status: IssueStatus         # draft | in_review | approved | sent
    metrics: IssueMetrics       # italy_count, foreign_count, section_counts

class NewsletterSlot:
    position: int               # 1-12
    section: Section            # top_priority | clinical | regulatory | device | cme
    item_id: UUID
    editorial: EditorialBlock
```

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
```
