# Architecture: Italian Pediatrics Newsletter Engine

## System Overview

Deterministic pipeline with LLM "in the loop" on specific tasks. The LLM is a transformation engine, not the final arbiter of truth.

```
[Sources] -> [Ingestion] -> [Dedup] -> [Classification] -> [Scoring] -> [Synthesis] -> [Verification] -> [Composer] -> [Review] -> [Delivery]
```

---

## Pipeline Stages

### 1. Ingestion (Daily, Mon-Fri)
- **Input**: Source registry (whitelist)
- **Connectors**: RSS/Atom parser, HTTP scraper, PDF fetcher
- **Output**: Raw `NewsItem` records in DB
- **Normalization**: clean text, detect language, parse timestamps, extract metadata (source, author, institution, document type), canonical URL

### 2. Deduplication
- **URL hash**: exact match on canonical URL
- **Title similarity**: embedding cosine similarity > 0.92 = duplicate
- **Cluster**: "same news in different sources" grouped, primary source preferred
- **Output**: Deduplicated candidate set

### 3. Classification (LLM - structured output)
- **Taxonomy tags**: from defined enum (see docs/PRD.md)
- **Geo**: IT / EU / GLOBAL
- **Setting**: territory / hospital / mixed
- **Document type**: safety_communication / guideline / consensus / surveillance_report / legal_update / event
- **Device-related flag**
- **Model**: economic model (GPT-5 mini or equivalent)

### 4. Scoring
- **7-dimension weighted scoring** (see docs/PRD.md for weights)
- **Hard rules applied**: reliability gate, transferability multiplier, noise penalties
- **Output**: Scored and ranked candidate list (top 20 for synthesis)

### 5. Synthesis (LLM - structured output, primary model)
- **Evidence extraction**: 3-8 key passages from source content ("supporting snippets")
- **Editorial pack** (schema-first):
  - `headline_operational` (max 90 chars)
  - `why_it_matters` (1 sentence)
  - `what_to_do` (2-4 bullet actions)
  - `summary` (3-6 lines)
  - `citations` (claim -> source_url -> supporting_passage)
  - `confidence` (high/medium/low)
- **Model**: GPT-5.4 via Responses API + Structured Outputs

### 6. Verification
- **Rule**: If claim not supported by extracted snippets -> downgrade confidence or block
- **Cross-source check**: When possible (AIFA <-> EMA, ISS <-> Ministry)
- **Output**: Verified editorial packs with final confidence

### 7. Composer (Weekly, Friday or Monday AM)
- **Slot constraints**: 12 items total
  - Top 3, Clinical 2-3, Regulatory 1-2, Device/Test 2, CME 1-2
- **Ratio enforcement**: 70% IT / 30% foreign on final slots
- **Subject line**: Benefit-driven, 2 A/B variants
- **Output**: Complete newsletter (HTML + plain text)

### 8. Human Review
- **Mandatory**: Top 3 items, prescriptive implications, privacy/regulatory, device/IVD safety
- **Sample-based**: 20% rotation on remaining items
- **Interface**: Minimal FastAPI web app (approve/reject/edit per item)

### 9. Delivery
- **ESP**: SendGrid or Postmark
- **Headers**: RFC 8058 one-click unsubscribe, SPF/DKIM/DMARC
- **BCC-based**: Privacy-first recipient handling
- **Tracking**: Opens, clicks per item, feedback collection

---

## Data Model

See `src/models/` for Pydantic definitions. Core entity is `NewsItem` matching the schema in Section 7 of the blueprint (docs/PRD.md references).

Key entities:
- `Source` - registry entry with tier, type, URL, reliability
- `RawContent` - ingested content before processing
- `NewsItem` - full item with classification, scoring, editorial
- `Newsletter` - composed issue with slot assignments
- `ReviewDecision` - human review audit trail

---

## Tech Stack (MVP)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.12+ | Team expertise, ML/NLP ecosystem |
| Data models | Pydantic v2 | Strict typing, structured outputs |
| Database | PostgreSQL + pgvector | Rich queries + embedding similarity |
| DB migrations | Alembic | Standard, reversible |
| ORM | SQLAlchemy 2.0 | Async support, mature |
| LLM primary | OpenAI GPT-5.4 (Responses API) | Context, structured outputs, tools |
| LLM triage | GPT-5 mini | Classification, cheap |
| Orchestration | Prefect | DAG pipelines, retry, observability |
| HTTP | httpx | Async, timeouts, connection pooling |
| RSS | feedparser | Standard, battle-tested |
| Email ESP | SendGrid | Deliverability, analytics, API |
| Review UI | FastAPI + Jinja2 | Minimal, sufficient |
| Testing | pytest + pytest-asyncio | Standard |
| Linting | ruff | Fast, comprehensive |
| Type checking | pyright (strict) | Catches hallucinated APIs |

---

## Directory Structure

```
Oykos-Newsletter/
  .github/
    copilot-instructions.md
  .vibe/
    STATE.md
    backlog.md
    decisions/
    sessions/
  docs/
    PRD.md
    architecture.md
    data-model.md
    scoring.md
    sources.md
  specs/                          # Per-slice, deleted after merge
  src/
    oykos/
      __init__.py
      config.py                   # Settings via pydantic-settings
      models/
        __init__.py
        source.py                 # Source registry model
        taxonomy.py               # Taxonomy enums
        news_item.py              # Core NewsItem model
        newsletter.py             # Composed newsletter model
        review.py                 # Review decision model
      ingestion/
        __init__.py
        rss.py                    # RSS/Atom connector
        scraper.py                # HTTP scraper
        normalizer.py             # Content normalization
      processing/
        __init__.py
        dedup.py                  # Deduplication engine
        classifier.py             # Taxonomy classification
        scorer.py                 # 7-dimension scoring
        ranker.py                 # Candidate ranking with constraints
      synthesis/
        __init__.py
        llm_client.py             # OpenAI wrapper
        extractor.py              # Evidence snippet extraction
        editorial.py              # Editorial pack generation
        verifier.py               # Claim verification
      composition/
        __init__.py
        composer.py               # Weekly slot composer
        templates/                # HTML/text templates
        subject.py                # Subject line generation
      delivery/
        __init__.py
        email.py                  # ESP integration
        deliverability.py         # Headers, unsubscribe
        feedback.py               # Feedback collection
      review/
        __init__.py
        app.py                    # FastAPI review interface
      db/
        __init__.py
        engine.py                 # DB connection
        repository.py             # CRUD operations
        migrations/               # Alembic
      pipeline/
        __init__.py
        daily.py                  # Daily ingestion flow
        weekly.py                 # Weekly composition flow
        alerts.py                 # Trigger alert flow
  tests/
    unit/
    integration/
    e2e/
    fixtures/
    conftest.py
  scripts/
    vibe-check.ps1
  pyproject.toml
  README.md
```

---

## Non-Negotiable Principles
1. **Source -> claim traceability**: every item has citations and supporting sentences
2. **Uncertainty management**: unknown = declare (confidence: low) or exclude
3. **Human-in-the-loop targeted**: mandatory on high-risk, sampling on rest
4. **Deterministic workflow**: LLM as transformation engine, not truth arbiter
5. **Schema-first**: all LLM outputs use Structured Outputs with Pydantic schemas
