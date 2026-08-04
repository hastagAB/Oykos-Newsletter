# Architecture: Italian Pediatrics Newsletter Engine

## System Overview

Deterministic pipeline with LLM "in the loop" on specific tasks. The LLM is a transformation engine, not the final arbiter of truth.

```
[Sources] -> [Ingestion] -> [Dedup] -> [Classification] -> [Scoring] -> [Gates]
          -> [Ranking] -> [Synthesis] -> [Verification] -> [Composer]
          -> [Human Review] -> [WordPress] -> [Email]
```

Ranking sits **before** synthesis. That ordering is the cost posture of the whole
system: see [Cost control](#cost-control).

Where this diverges from the product blueprint, see
[deviations.md](deviations.md).

---

## Pipeline Stages

### 1. Ingestion (Daily, Mon-Fri)
- **Input**: Source registry (whitelist)
- **Connectors**: RSS/Atom parser (`ingestion/rss.py`), controlled HTML scraper
  (`ingestion/scraper.py`). The scraper is what makes the Italian institutional
  core feed reachable - Ministry, AIFA, ISS, SISAC, Garante, Agenas, ECDC and EMA
  publish no usable RSS.
- **Output**: Raw `NewsItem` records in DB
- **Normalization**: clean text, detect language, parse timestamps, extract metadata (source, author, institution, document type), canonical URL

### 2. Deduplication and penalties
- **URL match**: exact match on the canonical URL (`ingestion/normalizer.py`)
- **Title similarity**: >= 0.85 against titles from the last 28 days is a
  duplicate and the item is dropped (`ingestion/dedup.py`)
- **Penalty band**: 0.75-0.85 is "same news rewritten" and earns the duplicate
  penalty instead (`processing/scoring.detect_penalties`)
- **Other noise penalties**: paywall, press release without data, single source
- **Output**: Deduplicated candidate set with penalties recorded

There is no embedding or vector similarity step. See [deviations.md](deviations.md).

### 3. Classification (LLM - structured output)
- **Taxonomy tags**: from defined enum (see docs/PRD.md), including
  `research_evidence` and `ai_digital_health`
- **Geo**: IT / EU / GLOBAL
- **Setting**: territory / hospital / mixed
- **Document type**: safety_communication / guideline / consensus / surveillance_report / legal_update / event / news / study
- **Device-related flag**
- **7 subscores**, produced in the same call
- **Model**: `OPENAI_TRIAGE_MODEL` (GPT-5 mini by default)

### 4. Scoring and gates
- **7-dimension weighted scoring** (`processing/scoring.py`, see docs/scoring.md)
- **Transferability multiplier** applied to foreign items (0.65 - 0.95)
- **Noise penalties** applied to the raw score
- **Three selection gates** plus exclusion criteria (`processing/gates.py`).
  A low-trust source or a preprint is excluded here, not demoted.
- **Output**: Scored, gated candidate pool in the DB

### 5. Ranking and shortlist (weekly)
- `processing/ranker.rank_and_select` fills section minimums first, then spends
  the remaining budget by score, under hard Italy/foreign caps
- The weekly pipeline shortlists `MAX_NEWSLETTER_ITEMS + EDITORIAL_HEADROOM` (3)
  items. Everything downstream operates on the shortlist only.

### 6. Synthesis (LLM - structured output, primary model)
- **Evidence extraction**: key passages from source content, verbatim-checked -
  a quote not present in the source is discarded rather than cited
- **Editorial pack** (schema-first):
  - `headline_operational` (max 90 chars)
  - `why_it_matters` (1 sentence)
  - `what_to_do` (2-4 bullet actions)
  - `summary` (3-6 lines)
  - `citations` (claim -> source_url -> supporting_passage)
  - `confidence` (high/medium/low)
- **Model**: `OPENAI_MODEL` (GPT-5.4 by default) via Responses API + Structured Outputs

### 7. Verification
- **Rule**: a claim not supported by the extracted snippets downgrades confidence;
  no evidence at all, or two or more unsupported claims, blocks the item
- **Cross-source check**: AIFA <-> EMA, ISS <-> Ministry. A second institutional
  source covering the same ground restores medium confidence to high.
- **Output**: Verified editorial packs with final confidence

### 8. Composer
- **Slot constraints**: 12 items total
  - Top 3, Clinical 2-3, Regulatory 1-2, Device/Test 1-2, CME 1-2
- **Ratio enforcement**: 8 Italian / 4 foreign slots, hard caps. A thin week
  produces a shorter issue rather than a lopsided one.
- **Top 3**: at most 2 Italian items, so the section is never all-domestic
- **Header furniture**: TL;DR (3 lines), reading time clamped to 6-8 minutes
- **Subject line + preheader**: `newsletter/subject.py`, on the triage model
- **Closing CTA**: every issue ends with `CTA_TITLE` / `CTA_SUBTITLE` and a
  `CTA_BUTTON` linking to `CTA_URL`, in both HTML and plain text
- **Output**: Complete newsletter (HTML + plain text)

### 9. Human Review
- **Scope**: every item in the issue. `compose_newsletter` sets
  `needs_human_review = True` on all selected items - no sampling, no
  auto-approval path.
- **Gate**: the weekly pipeline holds the issue in `IN_REVIEW` while any item
  still needs sign-off
- **Interface**: `/review`, served by `web/review.py`
- **SLA escape hatch**: `AUTO_SEND_AFTER_HOURS` (default `0` = never). When set,
  an issue past the deadline ships with the cleared items only and drops the
  rest; it never sends unreviewed content.

### 10. Publishing
- **Target**: the WordPress REST API, `POST /wp-json/wp/v2/posts`
  (`delivery/wordpress.py`)
- **Auth**: HTTP Basic with a WordPress Application Password
- **Ordering**: publish first, then send, so the email can carry a working
  "Leggi online" link. The returned URL is stored on `Newsletter.public_url`.
- **Failure**: logged, returns an empty string, delivery proceeds without the
  link. Empty `WORDPRESS_URL` skips the step entirely.
- See [wordpress.md](wordpress.md)

### 11. Delivery
- **Transport**: SMTP (Zoho by default), one message per subscriber over a
  shared, throttled connection
- **Headers**: RFC 8058 one-click unsubscribe, List-Id; SPF/DKIM/DMARC on the
  sending domain (see docs/deliverability.md)
- **Privacy**: recipients are never disclosed to each other
- **Tracking**: feedback micro-survey per issue

---

## Cost control

The expensive call is editorial synthesis on the primary model. Three decisions
keep the bill proportional to what actually ships:

1. **Rank before writing.** `run_weekly_pipeline` gates and ranks the candidate
   pool first, then calls `build_editorial` on a shortlist of
   `max_newsletter_items + EDITORIAL_HEADROOM` items. Copy is never written for
   an item that has not already earned a slot. The headroom of 3 covers items
   that verification blocks.
2. **Triage model for everything cheap.** Classification, the 7 subscores and
   the subject line all run on `OPENAI_TRIAGE_MODEL`. The primary model is used
   for evidence extraction, synthesis and verification only.
3. **Provider is configuration, not code.** `OPENAI_MODEL`,
   `OPENAI_TRIAGE_MODEL` and `OPENAI_BASE_URL` point the whole system at any
   model or OpenAI-compatible endpoint - a cheaper tier, a local runtime, a
   different vendor - with no code change.

Daily classification is additionally capped at `MAX_CLASSIFY_PER_RUN` (60) items
per run.

---

## Operating rhythm

| Command | When | What it does |
|---------|------|--------------|
| `oykos ingest` | Mon-Fri | Ingest, classify, score, gate, evaluate alerts. Never sends the newsletter. |
| `oykos compose` | Weekly | Rank, shortlist, synthesise, verify, compose. Lands in the review queue. |
| `oykos send` | After review | Publishes to WordPress then delivers issues an editor approved. Safe to run often. |
| `oykos run` | - | Ingest then compose, in order. |
| `oykos serve` | Always | Subscriber pages, preferences, archive, feedback and the review workbench. |
| `oykos check-smtp` | On demand | Connects, authenticates and probes the From address. Sends nothing. |
| `oykos check-sources` | On demand | Fetches every enabled source concurrently, prints OK/DEAD and item counts, exits non-zero if nothing works. |

Trigger alerts are capped at `MAX_ALERTS_PER_MONTH` (default 2) in any rolling
30-day window, and never fire twice for the same item.

**There is no workflow engine.** The pipeline is plain async functions in
`pipeline/{daily,weekly,runner}.py`, driven by the CLI. Scheduling is cron, a
systemd timer, or whatever the host provides; `docker-compose.yml` exposes the
three jobs as `pipeline`, `compose-issue` and `send` services under the `cron`
profile. Retries live in the OpenAI and httpx clients; run health is visible
through structured logs and `HEALTHCHECK_PING_URL`.

---

## Editorial review

An issue is never delivered straight from composition. `oykos compose` leaves it
in `IN_REVIEW`, and the workbench at `/review` is where an editor acts:

1. `/review` lists issues with a per-issue count of outstanding decisions.
2. `/review/{week}` shows every item with its review reason, confidence,
   unsupported claims and sources.
3. Each item can be approved, edited (headline, why, actions, detail) or
   rejected. Rejection removes it from the issue and renumbers the rest.
4. Approving the issue is blocked until **every** item has a decision.
5. "Approva e invia ora" publishes and delivers immediately; otherwise
   `oykos send` picks it up.

Every decision is written to `review_decisions`, which is what the
corrections-rate KPI reads.

Access is a shared `REVIEW_TOKEN` exchanged for an HMAC-signed, httponly,
SameSite=strict session cookie scoped to `/review`. With no token configured the
router returns 404 for every path, so a misconfigured deployment cannot expose
an open approval surface.

---

## Data Model

See `src/oykos/models/` for Pydantic definitions. Core entity is `NewsItem`.
The canonical field-by-field reference is [data-model.md](data-model.md).

Key entities:
- `Source` - registry entry with tier, type, URL, reliability
- `NewsItem` - full item with content, classification, scoring, gating, editorial
- `Newsletter` - composed issue with slot assignments and `public_url`
- `ReviewDecision` - human review audit trail
- `Subscriber` - double opt-in record with preferences

---

## Tech Stack (MVP)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.12+ | Team expertise, ML/NLP ecosystem |
| Data models | Pydantic v2 | Strict typing, structured outputs |
| Database | PostgreSQL (prod) / SQLite (dev) | Same SQLAlchemy code on both; no pgvector, dedup is string-based |
| DB migrations | Alembic | Standard, reversible |
| ORM | SQLAlchemy 2.0 | Async support, mature |
| LLM primary | OpenAI GPT-5.4 (Responses API) | Context, structured outputs |
| LLM triage | GPT-5 mini | Classification, subscores, subject lines. Cheap |
| LLM provider | Configurable via `OPENAI_BASE_URL` | Any OpenAI-compatible endpoint, no code change |
| Orchestration | Plain async functions + cron | Three linear commands; a DAG engine bought nothing |
| HTTP | httpx | Async, explicit timeouts, connection pooling |
| RSS | feedparser | Standard, battle-tested |
| Scraping | BeautifulSoup | Tier-1 institutional sources publish no usable RSS |
| Email | SMTP via `smtplib` (Zoho by default) | Provider-agnostic; only `smtp_*` config is vendor-specific |
| Web publishing | WordPress REST API | The site already exists; gives the email a real archive target |
| Web UI | FastAPI + Jinja2 | Subscriber pages and the review workbench |
| Testing | pytest + pytest-asyncio | Standard |
| Linting | ruff | Fast, comprehensive |
| Type checking | pyright (strict) | Catches hallucinated APIs |

---

## Directory Structure

```
Oykos-Newsletter/
  .github/copilot-instructions.md
  .github/workflows/ci.yml
  .vibe/
    STATE.md
    backlog.md
    decisions/ADR-001-blueprint-conformance.md
    sessions/
  docs/
    PRD.md strategy.md              # the blueprint, left as specified
    deviations.md                   # where the build departs from it, and why
    architecture.md data-model.md scoring.md sources.md
    wordpress.md deliverability.md
  migrations/versions/              # Alembic
  src/oykos/
    __main__.py                     # CLI: ingest | compose | send | run | serve
                                    #      check-smtp | check-sources
    config.py                       # pydantic-settings
    models/
      taxonomy.py                   # enums
      source.py                     # source registry (50 entries)
      news_item.py                  # NewsItem, Newsletter, Gating
    ingestion/
      rss.py                        # RSS/Atom connector
      scraper.py                    # controlled HTML scraper (Tier-1 core feed)
      normalizer.py                 # canonical URL, HTML cleaning
      dedup.py                      # canonical URL + title similarity
      health.py                     # oykos check-sources
      orchestrator.py               # daily ingestion across the registry
    llm/
      client.py                     # Responses API + Structured Outputs
      classifier.py                 # taxonomy + 7 subscores (triage model)
      extraction.py                 # evidence snippets, verbatim-checked
      synthesis.py                  # 5-block editorial from snippets
      verification.py               # grounding check, downgrade or block
    processing/
      gates.py                      # 3 selection gates + exclusion criteria
      scoring.py                    # 7-dimension scoring, transferability,
                                    # detect_penalties (noise penalties)
      ranker.py                     # section quotas, hard 70/30 caps
    newsletter/
      composer.py                   # slots, TL;DR, reading time
      template.py                   # HTML + plain text, closing CTA
      subject.py                    # subject + preheader (triage model)
    alerts/
      triggers.py                   # 4 hard-event categories
      pipeline.py                   # delivery with monthly cap
      template.py
    delivery/
      email_sender.py               # SMTP, RFC 8058 headers, Bcc privacy
      wordpress.py                  # WordPress REST publishing
      preflight.py                  # oykos check-smtp
    db/
      engine.py tables.py repository.py subscribers.py
    pipeline/
      daily.py                      # Mon-Fri: ingest, classify, score, gate, alert
      weekly.py                     # rank, synthesise, compose, review-gate, deliver
      runner.py                     # entry points and DB wiring
    observability/
      logging.py metrics.py
    web/
      app.py                        # app factory, lifespan, router mounting
      public.py                     # subscribe, confirm, preferences, archive, feedback
      review.py                     # editorial review workbench
      design.py                     # shared design system
  tests/
    unit/ integration/ e2e/ fixtures/
  scripts/
    run_pipeline.py send_test_email.py vibe-check.ps1
```

Note: `detect_penalties` lives in `processing/scoring.py`. There is no separate
`processing/penalties.py`, and no `processing/review_policy.py` - every item is
reviewed.

---

## Non-Negotiable Principles
1. **Source -> claim traceability**: every item has citations and supporting sentences
2. **Uncertainty management**: unknown = declare (confidence: low) or exclude
3. **Human-in-the-loop on everything**: every published item is signed off by a person
4. **Deterministic workflow**: LLM as transformation engine, not truth arbiter
5. **Schema-first**: all LLM outputs use Structured Outputs with Pydantic schemas
6. **Spend follows what ships**: nothing expensive runs on an item that has not
   already earned a slot

---

## Deviations from the blueprint

Radar sections, Decision Cards, A/B subject testing, embedding-based semantic
dedup, referrals, PDF ingestion, Prefect orchestration, the offline evaluation
harness and the auto-approval review policy are all specified in `docs/PRD.md`
and deliberately not built.

[deviations.md](deviations.md) records each one: what the blueprint asked for,
what ships instead, why it was cut, and the concrete trigger that would justify
building it. That file is the honest reconciliation between blueprint and code;
`PRD.md` and `strategy.md` are left describing the original intent.
