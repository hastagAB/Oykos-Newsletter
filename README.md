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
  <img src="https://img.shields.io/badge/tests-143-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage%20floor-65%25-brightgreen" alt="Coverage floor">
</p>

---

## What is Oykos?

Oykos is a deterministic pipeline with LLM-in-the-loop that aggregates news from a 50-source registry, scores them on 7 clinical dimensions, generates Italian-language editorial content, publishes each issue to WordPress, and delivers a weekly newsletter to pediatricians. Every item answers three questions:

1. **What happened?**
2. **Why does it matter for a PLS?**
3. **What changes tomorrow morning in the studio?**

The system ensures no article is ever repeated across issues, enforces a 70/30 Italy/foreign ratio, and falls back to a backlog pool when fresh candidates are scarce. No issue is ever delivered without a human signing off on every item in it.

---

## Pipeline Overview

The pipeline is plain async Python driven by the CLI. There is no workflow
engine: `oykos ingest`, `oykos compose` and `oykos send` are three commands you
put on cron.

```
--- daily, Mon-Fri: oykos ingest --------------------------------------------

Source registry (50: RSS + controlled scrape)
      |
      v
  1. Ingest -------> Dedup: canonical URL, then title similarity >= 0.85
      |              over a 28-day window. Noise penalties recorded.
      v
  2. Classify -----> Triage model: taxonomy, geo, setting, 7 subscores
      |
      v
  3. Score + gate -> Weighted 0-100 score, transferability, 3 selection gates
      |              Trigger alerts evaluated (capped at 2 per 30 days)
      v
--- weekly: oykos compose ---------------------------------------------------

  4. Rank ---------> Section quotas + 70/30 split produce a shortlist of
      |              MAX_NEWSLETTER_ITEMS + 3. Nothing else is written up.
      v
  5. Synthesize ---> Evidence extraction, editorial pack, claim verification
      |              (the expensive model, shortlist only)
      v
  6. Compose ------> Slots, TL;DR, reading time, subject line (triage model)
      |
      v
  7. Review -------> Issue held IN_REVIEW. Every item needs sign-off at /review
      |
      v
--- after sign-off: oykos send ----------------------------------------------

  8. Publish ------> POST to the WordPress REST API, store public_url
      |              so the email can link "Leggi online"
      v
  9. Send ---------> SMTP, one message per subscriber, items marked sent
```

Each phase is logged with structured output. Failed items are skipped gracefully
without breaking the pipeline. Ranking runs **before** synthesis on purpose: the
primary model only ever writes copy for items that have already earned a slot.

---

## Quick Start

### Prerequisites

- Python 3.12+
- An OpenAI API key, or any OpenAI-compatible endpoint via `OPENAI_BASE_URL`
- An SMTP mailbox. The defaults target Zoho Mail; see [docs/deliverability.md](docs/deliverability.md)
- Optional: a WordPress site with an Application Password; see [docs/wordpress.md](docs/wordpress.md)

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

# OpenAI (or any OpenAI-compatible provider)
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-5.4
OPENAI_TRIAGE_MODEL=gpt-5-mini

# SMTP delivery (defaults target Zoho Mail's EU data centre)
SMTP_HOST=smtp.zoho.eu
SMTP_PORT=465
SMTP_USERNAME=you@yourdomain.it
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=you@yourdomain.it

# Editorial review - without this the review UI refuses to serve
REVIEW_TOKEN=

# WordPress publishing - leave empty to disable, email still sends
WORDPRESS_URL=
WORDPRESS_USER=
WORDPRESS_APP_PASSWORD=
```

The legacy `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` variables still resolve to
`SMTP_USERNAME` / `SMTP_PASSWORD`.

See [.env.example](.env.example) for all available options.

### Run the Pipeline

The engine runs on two rhythms plus a delivery step:

```bash
# Daily, Mon-Fri: ingest, classify, score, gate, evaluate trigger alerts.
# Never sends the newsletter.
oykos ingest

# Weekly: rank, shortlist, synthesise, verify, compose.
# The issue lands in the editorial review queue.
oykos compose

# After an editor signs off: publish to WordPress, then deliver. Safe to run often.
oykos send

# Ingest then compose, in order.
oykos run

# Web server: subscriber pages, preferences, archive, feedback, review workbench.
oykos serve
```

### Preflight checks

Two commands verify the external boundaries without sending or writing anything:

```bash
# Connect, authenticate and probe the From address. No mail is delivered.
oykos check-smtp

# Fetch every enabled source concurrently and print OK/DEAD plus item counts.
# Exits non-zero if nothing came back at all.
oykos check-sources
```

`oykos check-sources` is the one to run when an issue comes up short: feed URLs
rot and scraper selectors drift, and a dead source otherwise fails silently.

### Review and approve an issue

An issue is never delivered straight from composition. Set a review token first:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # put in REVIEW_TOKEN
```

Then open `http://localhost:8000/review`, sign in with the token, and work
through the queue. Every item in an issue requires a decision - approve, edit or
reject - before the issue can be approved. There is no sampling and no
auto-approval path.

`AUTO_SEND_AFTER_HOURS` (default `0`, meaning never) is the only exception: when
set, an issue past the SLA ships with the cleared items only and drops the rest.

With `REVIEW_TOKEN` unset the review interface returns 404 for every path, so a
misconfigured deployment cannot expose an open approval surface.

### Send a Test Email

```bash
python scripts/send_test_email.py
```

### Publish to WordPress

Each issue is POSTed to `WORDPRESS_URL/wp-json/wp/v2/posts` **before** the email
goes out, so the email footer can link back to a live "Leggi online" page. Auth
is HTTP Basic with a WordPress **Application Password** (Users > Profile >
Application Passwords, WordPress 5.6+, HTTPS required), not the account password.

Leaving `WORDPRESS_URL` empty disables publishing; the pipeline still composes,
reviews and sends email exactly as before. A publishing failure is logged and
never blocks delivery - the issue just ships without the online link.

See [docs/wordpress.md](docs/wordpress.md).

---

## Project Structure

```
Oykos-Newsletter/
|
|- src/oykos/                   # Application source code
|   |- __main__.py              # CLI: ingest | compose | send | run | serve
|   |                           #      check-smtp | check-sources
|   |- config.py                # Pydantic-settings configuration
|   |
|   |- models/                  # Core data models (Pydantic v2)
|   |   |- news_item.py         # NewsItem, NewsletterSlot, Newsletter
|   |   |- source.py            # Source registry (50 sources, 4 tiers)
|   |   |- taxonomy.py          # Enums: Section, Geo, Tier, Confidence, TaxonomyTag
|   |
|   |- ingestion/               # Fetching and normalization
|   |   |- rss.py               # Async RSS/Atom parser (feedparser + httpx)
|   |   |- scraper.py           # Controlled HTML scraper (Tier-1 institutional feed)
|   |   |- normalizer.py        # URL canonicalization, HTML cleaning
|   |   |- dedup.py             # Canonical URL + title similarity (0.85 / 28 days)
|   |   |- health.py            # `oykos check-sources`
|   |   |- orchestrator.py      # Daily ingestion across the registry
|   |
|   |- llm/                     # OpenAI integration
|   |   |- client.py            # Responses API + Structured Outputs
|   |   |- classifier.py        # Taxonomy + 7 subscores (triage model)
|   |   |- extraction.py        # Evidence snippets, verbatim-checked
|   |   |- synthesis.py         # Editorial generation (headline, why, actions)
|   |   |- verification.py      # Grounding check: downgrade or block
|   |
|   |- processing/              # Gating, scoring and ranking
|   |   |- gates.py             # 3 selection gates + exclusion criteria
|   |   |- scoring.py           # 7-dimension scoring, transferability, penalties
|   |   |- ranker.py            # Section quotas, 70/30 split
|   |
|   |- newsletter/              # Composition and rendering
|   |   |- composer.py          # Slot selection, TL;DR, reading time
|   |   |- template.py          # Jinja2 HTML + plain text, closing CTA
|   |   |- subject.py           # Subject line + preheader (triage model)
|   |
|   |- delivery/                # Outbound
|   |   |- email_sender.py      # SMTP sender, RFC 8058 headers, Bcc privacy
|   |   |- wordpress.py         # WordPress REST publishing
|   |   |- preflight.py         # `oykos check-smtp`
|   |
|   |- web/                     # FastAPI surface
|   |   |- app.py               # App factory, lifespan, router mounting
|   |   |- public.py            # Subscribe, confirm, preferences, archive, feedback
|   |   |- review.py            # Editorial review workbench
|   |   |- design.py            # Shared design system
|   |
|   |- db/                      # Database layer (SQLAlchemy 2.0 async)
|   |   |- engine.py            # Engine + session factory
|   |   |- tables.py            # ORM table definitions
|   |   |- repository.py        # News item + newsletter + review CRUD
|   |   |- subscribers.py       # Subscriber repository
|   |
|   |- alerts/                  # Trigger-based urgent alerts
|   |   |- triggers.py          # 4 hard-event categories
|   |   |- pipeline.py          # Alert delivery + monthly cap
|   |   |- template.py          # Alert HTML/text rendering
|   |
|   |- pipeline/                # Orchestration (plain async, no workflow engine)
|   |   |- daily.py             # Mon-Fri: ingest, classify, score, gate, alert
|   |   |- weekly.py            # Rank, synthesise, compose, review-gate, deliver
|   |   |- runner.py            # Entry points and DB wiring
|   |
|   |- observability/           # Logging and metrics
|       |- logging.py           # Structured JSON logging
|       |- metrics.py           # Quality metrics and reporting
|
|- tests/                       # 139 test functions over the critical paths
|   |- unit/                    # Unit tests (mocked externals)
|   |- integration/             # Integration tests (real SQLite DB)
|   |- e2e/                     # End-to-end tests
|   |- fixtures/                # Shared test data
|
|- migrations/                  # Alembic
|- scripts/                     # run_pipeline.py, send_test_email.py, vibe-check.ps1
|- docs/                        # See the Documentation table below
|
|- .env.example                 # Environment variable template
|- pyproject.toml               # Project metadata, deps, tool config
|- CHANGELOG.md                 # Release history
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
- Source trust <= 2: the item fails the reliability gate and is excluded outright
- Preprints are excluded outright, never demoted
- Foreign items: transferability multiplier (0.65 - 0.95)
- Noise penalties: duplicates (-10), unverifiable paywall (-10), press release without data (-20), single source (-5)

See [docs/scoring.md](docs/scoring.md) for the gates, penalty thresholds and
composition constraints.

---

## Source Registry

Oykos monitors 50 sources across 4 tiers:

| Tier | Role | Examples |
|------|------|----------|
| **Tier 1 - Italy** | Core feed | Ministry of Health, AIFA, ISS/EpiCentro, SISAC, Garante Privacy, Agenas, SIP, FIMP, SIN |
| **Tier 2 - Europe** | High transferability | ECDC, EMA, European Journal of Pediatrics, Archives of Disease in Childhood, EAP |
| **Tier 3 - Global** | Conditional transfer | Lancet Child, JAMA Pediatrics, AAP, WHO, NICE, Nature Medicine, npj Digital Medicine, Lancet Digital Health |
| **Radar tier** | Triangulation only | Bambino Gesu, Meyer, Gaslini, UPPA, Medico e Bambino |

The Radar **tier** is a source-trust label, not a newsletter section. Items from
low-trust sources are triangulation material; they do not get published in a
section of their own.

See [docs/sources.md](docs/sources.md) for the full registry, and run
`oykos check-sources` to see which feeds are currently alive.

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
5. **Sources (2-3 links) + confidence badge** (High/Medium/Low)

Every issue closes with a call to action - "Inizia a risparmiare 1 ora al giorno
nella tua attivita pediatrica" and a "Scopri Oykos" button pointing at `CTA_URL`
(default `https://oykomed.it`) - in both the HTML and the plain text rendering.
When the issue was published to WordPress the footer also carries a
"Leggi online" link back to the post.

---

## Development

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/oykos --cov-report=term-missing

# Single test file
pytest tests/unit/test_editorial_logic.py -v
```

### Quality Gates

```powershell
# Run all gates (lint + format + types + tests + coverage)
.\scripts\vibe-check.ps1
```

This runs:
1. **ruff check** - Linting (E, F, W, I, N, UP, S, B, and more)
2. **ruff format** - Formatting drift, advisory only (the source registry and ORM tables are deliberately one entry per line)
3. **pyright** - Strict type checking
4. **pytest** - 139 test functions over the critical paths, 65% coverage floor
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
| LLM provider | OpenAI SDK, any compatible endpoint | `OPENAI_BASE_URL` + `OPENAI_MODEL` + `OPENAI_TRIAGE_MODEL` swap the provider with no code change |
| Structured outputs | Responses API + Pydantic schemas | Type-safe LLM responses, validated at parse time |
| Cost posture | Rank first, synthesise second | Editorial copy is only written for shortlisted items; subject lines use the triage model |
| Orchestration | Plain async functions + cron | The pipeline is three linear commands; a workflow engine bought nothing |
| Database | SQLAlchemy async + SQLite/PostgreSQL | Async pipeline, easy local dev, production-ready |
| Email | SMTP (Zoho by default) | Provider-agnostic, one message per subscriber, RFC 8058 headers |
| Web archive | WordPress REST API | The site already exists; the email gets a real "Leggi online" target |
| Scoring | Deterministic 7-dim + LLM subscores | Reproducible rankings, LLM assists but doesn't decide |
| Dedup | Canonical URL, then title similarity | Simple, cheap, no embedding spend or vector store to operate |
| Review | Human sign-off on every item | Medical content; no sampling, no auto-approval |
| Backlog | 7-28 day unsent pool | Ensures newsletter always has enough quality content |

Where the code deliberately departs from the product blueprint, see
[docs/deviations.md](docs/deviations.md).

See [docs/architecture.md](docs/architecture.md) for the full design.

---

## Configuration Reference

All configuration is via environment variables (loaded from `.env`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | SQLAlchemy async connection string |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key (or compatible provider key) |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | API base URL (override for compatible providers) |
| `OPENAI_MODEL` | No | `gpt-5.4` | Primary model, used for editorial synthesis only |
| `OPENAI_TRIAGE_MODEL` | No | `gpt-5-mini` | Cheap model: classification, subscores, subject lines |
| `SMTP_HOST` | No | `smtp.zoho.eu` | SMTP host; must match your Zoho data centre |
| `SMTP_PORT` | No | `465` | 465 implicit SSL, 587 STARTTLS |
| `SMTP_USERNAME` | Yes | - | SMTP user (alias: `GMAIL_ADDRESS`) |
| `SMTP_PASSWORD` | Yes | - | SMTP password (alias: `GMAIL_APP_PASSWORD`) |
| `SENDER_EMAIL` | No | `SMTP_USERNAME` | From address; must be owned by the account |
| `RECIPIENT_EMAILS` | No | - | Legacy comma-separated fallback when there are no confirmed subscribers |
| `NEWSLETTER_TITLE` | No | `L'Essenziale in Pediatria` | Newsletter title |
| `MAX_NEWSLETTER_ITEMS` | No | `12` | Max items per issue |
| `ITALY_RATIO` | No | `0.7` | Target Italy/foreign ratio |
| `MAX_ALERTS_PER_MONTH` | No | `2` | Trigger alert cap per rolling 30 days |
| `REVIEW_TOKEN` | No | (empty) | Shared secret for `/review`. Empty disables the UI entirely |
| `AUTO_SEND_AFTER_HOURS` | No | `0` | Review SLA before shipping cleared items only. `0` waits forever |
| `WORDPRESS_URL` | No | (empty) | WordPress site root. Empty disables publishing |
| `WORDPRESS_USER` | No | (empty) | WordPress username |
| `WORDPRESS_APP_PASSWORD` | No | (empty) | WordPress **Application Password**, not the account password |
| `WORDPRESS_STATUS` | No | `publish` | `publish` or `draft` |
| `WORDPRESS_CATEGORY_ID` | No | `0` | Category to file issues under. `0` = site default |
| `CTA_URL` | No | `https://oykomed.it` | Target of the closing call to action |
| `BASE_URL` | No | `http://localhost:8000` | Public URL for confirmation/unsubscribe links |
| `PREVIEW_MODE` | No | `false` | Always hold the issue for review |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Documentation

| Document | Description |
|----------|-------------|
| [PRD](docs/PRD.md) | Product requirements, jobs-to-be-done, selection gates (the blueprint, not the build) |
| [Deviations](docs/deviations.md) | Where the shipped code deliberately departs from the blueprint, and what would change that |
| [Architecture](docs/architecture.md) | Pipeline stages, tech stack, data flow |
| [Data Model](docs/data-model.md) | Pydantic schemas for NewsItem, Newsletter, Source |
| [Scoring](docs/scoring.md) | 7-dimension weights, gates, noise penalties |
| [Sources](docs/sources.md) | Full source registry with tiers and feed URLs |
| [WordPress](docs/wordpress.md) | Publishing setup, Application Passwords, troubleshooting |
| [Deliverability](docs/deliverability.md) | SMTP setup, SPF/DKIM/DMARC, list hygiene |
| [Strategy](docs/strategy.md) | Product strategy, content taxonomy, editorial rules |
| [Developer Guide](DEVELOPER_GUIDE.md) | Deployment, infrastructure, troubleshooting |
| [Changelog](CHANGELOG.md) | Release history |

---

## License

Proprietary - Oykomed. All rights reserved.
