<p align="center">
  <strong>Oykos</strong><br>
  Italian Pediatrics Newsletter Engine
</p>

<p align="center">
  <em>AI-powered operational intelligence briefing for Italian Pediatricians of Free Choice (PLS)</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/license-proprietary-red" alt="License">
  <img src="https://img.shields.io/badge/tests-127%20passing-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-%E2%89%A590%25-brightgreen" alt="Coverage">
</p>

---

## What is Oykos?

Oykos is a deterministic pipeline with LLM-in-the-loop that aggregates news from 12+ pediatric sources, scores them on 7 clinical dimensions, generates Italian-language editorial content, and delivers a weekly newsletter to pediatricians. Every item answers three questions:

1. **What happened?**
2. **Why does it matter for a PLS?**
3. **What changes tomorrow morning in the studio?**

The system ensures no article is ever repeated across issues, enforces a 70/30 Italy/foreign ratio, and falls back to a backlog pool when fresh candidates are scarce.

---

## Pipeline Overview

```
RSS Sources (12)
      |
      v
  1. Ingest -------> Dedup against DB (URL match)
      |
      v
  2. Classify -----> Azure OpenAI: taxonomy, geo, section tags
      |
      v
  3. Score --------> 7-dimension weighted scoring (0-100)
      |
      v
  4. Synthesize ---> Editorial: headline, why, actions, confidence
      |
      v
  5. Compose ------> 8-12 items, section layout, ratio enforcement
      |
      v
  6. Render -------> HTML (responsive) + plain text
      |
      v
  7. Send ---------> Gmail SMTP, mark items as sent in DB
```

Each phase is logged with structured output. Failed items are skipped gracefully without breaking the pipeline.

---

## Quick Start

### Prerequisites

- Python 3.12+
- An Azure OpenAI deployment (GPT-5.2 or compatible)
- A Gmail account with an [app password](https://myaccount.google.com/apppasswords)

### Installation

```bash
git clone <repo-url> && cd Oykos-Newsletter

python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Database (SQLite for local dev)
DATABASE_URL=sqlite+aiosqlite:///oykos.db

# OpenAI
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o

# Gmail SMTP
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
SENDER_EMAIL=your-email@gmail.com
RECIPIENT_EMAILS=recipient@example.com
```

See [.env.example](.env.example) for all available options.

### Run the Pipeline

```bash
# Via console script
oykos

# Or directly
python -m oykos

# Or via script
python scripts/run_pipeline.py
```

### Send a Test Email

```bash
python scripts/send_test_email.py
```

---

## Project Structure

```
Oykos-Newsletter/
|
|- src/oykos/                   # Application source code
|   |- __main__.py              # CLI entry point
|   |- config.py                # Pydantic-settings configuration
|   |
|   |- models/                  # Core data models (Pydantic v2)
|   |   |- news_item.py         # NewsItem, NewsletterSlot, Newsletter
|   |   |- source.py            # Source registry (40+ sources, 4 tiers)
|   |   |- taxonomy.py          # Enums: Section, Geo, Tier, Confidence
|   |
|   |- ingestion/               # RSS fetching and normalization
|   |   |- rss.py               # Async RSS/Atom parser (feedparser + httpx)
|   |   |- normalizer.py        # URL canonicalization, HTML cleaning
|   |   |- dedup.py             # Deduplication engine
|   |   |- orchestrator.py      # Daily ingestion orchestration
|   |
|   |- llm/                     # OpenAI integration
|   |   |- client.py            # AsyncOpenAI wrapper
|   |   |- classifier.py        # Taxonomy classification (structured output)
|   |   |- synthesis.py         # Editorial generation (headline, why, actions)
|   |   |- verification.py      # Claim verification + confidence scoring
|   |
|   |- processing/              # Scoring and ranking
|   |   |- scoring.py           # 7-dimension weighted scoring engine
|   |   |- ranker.py            # Candidate ranking with hard rules
|   |
|   |- newsletter/              # Newsletter composition and rendering
|   |   |- composer.py          # Slot selection, section layout, ratio enforcement
|   |   |- template.py          # Jinja2 HTML + plain text rendering
|   |   |- subject.py           # Subject line generation
|   |
|   |- delivery/                # Email delivery
|   |   |- email_sender.py      # Gmail SMTP_SSL sender
|   |   |- review_api.py        # FastAPI human review interface
|   |
|   |- db/                      # Database layer (SQLAlchemy 2.0 async)
|   |   |- engine.py            # Engine + session factory
|   |   |- tables.py            # ORM table definitions
|   |   |- repository.py        # CRUD operations + sent tracking
|   |
|   |- alerts/                  # Trigger-based urgent alerts
|   |   |- triggers.py          # Alert trigger rules
|   |   |- pipeline.py          # Alert delivery pipeline
|   |   |- template.py          # Alert HTML/text rendering
|   |
|   |- pipeline/                # Pipeline orchestration
|   |   |- runner.py            # Full daily pipeline (7 phases)
|   |   |- weekly.py            # Weekly composition pipeline
|   |
|   |- observability/           # Logging and metrics
|       |- logging.py           # Structured JSON logging
|       |- metrics.py           # Quality metrics and reporting
|
|- tests/                       # Test suite (127 tests)
|   |- unit/                    # Unit tests (mocked externals)
|   |- integration/             # Integration tests (real SQLite DB)
|   |- e2e/                     # End-to-end tests
|   |- fixtures/                # Shared test data
|
|- scripts/                     # Automation scripts
|   |- run_pipeline.py          # Pipeline runner (thin wrapper)
|   |- send_test_email.py       # Email delivery test
|   |- vibe-check.ps1           # Quality gates (lint, format, types, tests)
|
|- docs/                        # Documentation
|   |- PRD.md                   # Product requirements document
|   |- architecture.md          # System architecture and pipeline design
|   |- data-model.md            # Pydantic schema reference
|   |- scoring.md               # 7-dimension scoring specification
|   |- sources.md               # Source registry (40+ sources, 4 tiers)
|   |- strategy.md              # Product strategy and content taxonomy
|
|- .env.example                 # Environment variable template
|- pyproject.toml               # Project metadata, deps, tool config
|- CHANGELOG.md                 # Release history
|- .gitignore                   # Git ignore rules
```

---

## Scoring Engine

Every article is scored on 7 dimensions (0-100 weighted total):

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| PLS Relevance | 22% | Impact on outpatient/triage decisions |
| Clinical Impact | 18% | Reduces risk or changes clinical management |
| Operational Impact | 15% | Changes workflow, timing, communication |
| Source Trust | 15% | Institutional/primary vs secondary source |
| Novelty | 10% | New vs already-covered in last 4 weeks |
| Actionability | 10% | Concrete "what to do tomorrow" |
| Urgency | 10% | Seasonal, time-sensitive, or immediate |

**Hard rules** override raw scores:
- Source trust <= 2: "Radar" only, cannot enter Top 5
- Foreign items: transferability multiplier (0.6 - 1.0)
- Noise penalties: duplicates (-10), unverifiable paywall (-10), press release without data (-20)

---

## Source Registry

Oykos monitors 40+ sources across 4 tiers:

| Tier | Role | Examples |
|------|------|----------|
| **Tier 1 - Italy** | Core feed | SIP, SIN, FIMP, AIFA, Ministry of Health, ISS/EpiCentro |
| **Tier 2 - Europe** | High transferability | ECDC, EMA, European Journal of Pediatrics, Archives of Disease in Childhood |
| **Tier 3 - Global** | Conditional transfer | Lancet Child, JAMA Pediatrics, AAP, Pediatric Research |
| **Radar** | Triangulation only | Bambino Gesu, Gaslini, UPPA, regional ASL updates |

See [docs/sources.md](docs/sources.md) for the full registry.

---

## Newsletter Format

Each issue contains 8-12 items organized by section:

| Section | Items | Purpose |
|---------|-------|---------|
| Top Priority | 1-3 | Must-read: highest-scoring items |
| Clinical | 2-3 | Respiratory, GI, dermatology, neuro-dev, triage |
| Regulatory | 1-2 | ACN, privacy, telemedicine, prescriptive |
| Device/Test | 1-2 | Evidence-based POCT, diagnostics, safety alerts |
| CME/Events | 1-2 | Training, congresses, Agenas ECM |

Every item follows a 5-block format:
1. **Operational headline** (max 90 chars)
2. **Why it matters** for a PLS (1 sentence)
3. **Do/avoid** actions (2-4 bullets)
4. **Clinical detail** (3-6 lines)
5. **Source + confidence badge** (High/Medium/Low)

---

## Development

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/oykos --cov-report=term-missing

# Single test file
pytest tests/unit/test_scoring.py -v
```

### Quality Gates

```powershell
# Run all gates (lint + format + types + tests + coverage)
.\scripts\vibe-check.ps1
```

This runs:
1. **ruff check** - Linting (E, F, W, I, N, UP, S, B, and more)
2. **ruff format** - Code formatting verification
3. **pyright** - Strict type checking
4. **pytest** - 127 tests with 90% coverage minimum
5. **ruff check --select S** - Security scan (Bandit rules)

### Code Style

- **Formatter**: ruff (Python 3.12 target)
- **Linter**: ruff with 20+ rule categories
- **Type checker**: pyright (strict mode)
- **Imports**: `from __future__ import annotations` in every module
- **Config**: All via environment variables through `pydantic-settings`
- **DB**: SQLAlchemy ORM only - no raw SQL
- **HTTP**: httpx async with explicit timeouts

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM provider | Azure OpenAI | Enterprise SLA, structured outputs, large context |
| Structured outputs | Pydantic schemas | Type-safe LLM responses, validated at parse time |
| Database | SQLAlchemy async + SQLite/PostgreSQL | Async pipeline, easy local dev, production-ready |
| Email | Gmail SMTP_SSL | Zero cost for MVP, app password auth |
| Scoring | Deterministic 7-dim + LLM subscores | Reproducible rankings, LLM assists but doesn't decide |
| Dedup | URL hash in DB | Simple, reliable, no false positives |
| Backlog | 7-28 day unsent pool | Ensures newsletter always has enough quality content |

See [docs/architecture.md](docs/architecture.md) for the full design.

---

## Configuration Reference

All configuration is via environment variables (loaded from `.env`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | SQLAlchemy connection string |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | API base URL (override for compatible providers) |
| `OPENAI_MODEL` | No | `gpt-4o` | Primary model name |
| `OPENAI_TRIAGE_MODEL` | No | `gpt-4o-mini` | Classification model |
| `GMAIL_ADDRESS` | Yes | - | Gmail sender address |
| `GMAIL_APP_PASSWORD` | Yes | - | Gmail app password |
| `SENDER_EMAIL` | No | `GMAIL_ADDRESS` | From address in emails |
| `RECIPIENT_EMAILS` | Yes | - | Comma-separated recipient list |
| `NEWSLETTER_TITLE` | No | `L'Essenziale in Pediatria` | Newsletter title |
| `MAX_NEWSLETTER_ITEMS` | No | `12` | Max items per issue |
| `ITALY_RATIO` | No | `0.7` | Target Italy/foreign ratio |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Documentation

| Document | Description |
|----------|-------------|
| [PRD](docs/PRD.md) | Product requirements, jobs-to-be-done, selection gates |
| [Architecture](docs/architecture.md) | Pipeline stages, tech stack, data flow |
| [Data Model](docs/data-model.md) | Pydantic schemas for NewsItem, Newsletter, Source |
| [Scoring](docs/scoring.md) | 7-dimension weights, hard rules, noise penalties |
| [Sources](docs/sources.md) | Full source registry with tiers and feed URLs |
| [Strategy](docs/strategy.md) | Product strategy, content taxonomy, editorial rules |
| [Changelog](CHANGELOG.md) | Release history |

---

## License

Proprietary - Oykomed. All rights reserved.
