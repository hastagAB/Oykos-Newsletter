# Oykos Newsletter Engine - Developer Guide

> Handoff documentation for deploying and operating the Oykos Newsletter Engine
> in your own infrastructure.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Configuration Reference](#configuration-reference)
4. [Local Development Setup](#local-development-setup)
5. [Database Setup](#database-setup)
6. [OpenAI / LLM Configuration](#openai--llm-configuration)
7. [Email / SMTP Configuration](#email--smtp-configuration)
8. [WordPress Publishing](#wordpress-publishing)
9. [Docker Deployment](#docker-deployment)
10. [Running the Pipeline](#running-the-pipeline)
11. [Web Server (Subscribers, Archive, Feedback)](#web-server)
12. [CI/CD](#cicd)
13. [Adapting to Your Infrastructure](#adapting-to-your-infrastructure)
14. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
                  +------------------+
                  |  Source registry |
                  |   (50 RSS and    |
                  |  scraped feeds)  |
                  +--------+---------+
                           |
                    1. Ingest + Dedup
                           |
                  +--------v---------+
                  |   PostgreSQL DB  |
                  |  (news_items,    |
                  |   newsletters,   |
                  |   subscribers)   |
                  +--------+---------+
                           |
              2. Classify + Score + Gate (triage model)
              3. Rank -> shortlist
              4. Synthesize + Verify (primary model)
              5. Compose + Render HTML
                           |
                  +--------v---------+
                  |  Human review    |
                  |  /review         |
                  |  every item      |
                  +--------+---------+
                           |
                  +--------v---------+
                  |    WordPress     |
                  |  /wp-json/wp/v2  |
                  |  -> public_url   |
                  +--------+---------+
                           |
                  +--------v---------+
                  |  Email Delivery  |
                  |  (SMTP, one msg  |
                  |   per subscriber)|
                  +------------------+

                  +------------------+
                  | FastAPI Web App  |
                  |  /subscribe      |
                  |  /confirm/{tok}  |
                  |  /preferences    |
                  |  /unsubscribe    |
                  |  /archive        |
                  |  /feedback       |
                  |  /review         |
                  +------------------+
```

**Key components:**

| Module | Purpose |
|--------|---------|
| `oykos.ingestion` | RSS fetching, controlled scraping, HTML cleaning, URL normalization, dedup, source health checks |
| `oykos.llm` | OpenAI client, classification, evidence extraction, editorial synthesis, claim verification |
| `oykos.processing` | Selection gates, 7-dimension scoring, noise penalties (`detect_penalties`), candidate ranking |
| `oykos.newsletter` | Composition (section quotas, IT/foreign caps), Jinja2 rendering with closing CTA, subject line |
| `oykos.delivery` | SMTP sender, WordPress publishing, SMTP preflight |
| `oykos.web` | Subscriber management, preferences, public archive, feedback, editorial review workbench |
| `oykos.db` | SQLAlchemy async ORM, repositories, Alembic migrations |
| `oykos.pipeline` | Daily and weekly flows as plain async functions, plus DB wiring |

There is no workflow engine. `pipeline/runner.py` exposes four entry points
(`run_daily`, `run_weekly`, `run_pipeline`, `send_pending`) that the CLI calls
directly; scheduling is cron or equivalent.

---

## Prerequisites

- **Python** >= 3.12
- **PostgreSQL** >= 14 (production) or SQLite (local dev)
- **OpenAI API key** (or any OpenAI-compatible endpoint)
- **SMTP credentials** (Zoho by default; any SMTP server works)
- **Optional: a WordPress site** (5.6+, HTTPS) with an Application Password

---

## Configuration Reference

All configuration is via **environment variables**, loaded from a `.env` file by
[pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | SQLAlchemy async connection string | `postgresql+asyncpg://user:pass@host:5432/oykos` |
| `OPENAI_API_KEY` | OpenAI API key (or compatible provider key) | `sk-proj-...` |
| `SMTP_USERNAME` | SMTP user. Legacy alias: `GMAIL_ADDRESS` | `newsletter@yourdomain.it` |
| `SMTP_PASSWORD` | SMTP password. Legacy alias: `GMAIL_APP_PASSWORD` | `xxxx xxxx xxxx xxxx` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for OpenAI-compatible providers (see [LLM section](#openai--llm-configuration)) |
| `OPENAI_MODEL` | `gpt-5.4` | Primary model. Used for evidence extraction, synthesis and verification only |
| `OPENAI_TRIAGE_MODEL` | `gpt-5-mini` | Cheap model: classification, subscores, subject lines |
| `OPENAI_TIMEOUT_SECONDS` | `120` | Per-request timeout |
| `OPENAI_MAX_RETRIES` | `3` | SDK-level retries |
| `SMTP_HOST` | `smtp.zoho.eu` | Must match your Zoho data centre (see docs/deliverability.md) |
| `SMTP_PORT` | `465` | 465 = implicit SSL, 587 = STARTTLS |
| `SMTP_USE_SSL` | `true` | Set `false` for STARTTLS on 587 |
| `SMTP_THROTTLE_SECONDS` | `1.0` | Pause between messages in a bulk send |
| `SMTP_MAX_PER_CONNECTION` | `50` | Recycle the SMTP connection after this many messages |
| `SENDER_EMAIL` | (same as `SMTP_USERNAME`) | "From" address. Must be owned by the authenticated account |
| `UNSUBSCRIBE_MAILTO` | (empty) | `mailto:` fallback for `List-Unsubscribe` |
| `RECIPIENT_EMAILS` | (empty) | Legacy comma-separated fallback, used only when there are no confirmed subscribers |
| `NEWSLETTER_TITLE` | `L'Essenziale in Pediatria` | Title shown in emails and archive |
| `MAX_NEWSLETTER_ITEMS` | `12` | Maximum items per issue |
| `ITALY_RATIO` | `0.7` | Target Italy/foreign news ratio (0.0 - 1.0) |
| `MIN_READING_MINUTES` / `MAX_READING_MINUTES` | `6` / `8` | Reading time clamp |
| `MAX_ALERTS_PER_MONTH` | `2` | Trigger alert cap per rolling 30 days |
| `REVIEW_TOKEN` | (empty) | Shared secret for `/review`. **Empty disables the review UI entirely** (fails closed) |
| `REVIEW_SESSION_HOURS` | `12` | Lifetime of the signed review session cookie |
| `AUTO_SEND_AFTER_HOURS` | `0` | Review SLA. `0` waits for a human indefinitely; when set, only cleared items ship |
| `WORDPRESS_URL` | (empty) | Site root, no trailing slash. Empty disables publishing |
| `WORDPRESS_USER` | (empty) | WordPress username |
| `WORDPRESS_APP_PASSWORD` | (empty) | Application Password, **not** the account password |
| `WORDPRESS_STATUS` | `publish` | `publish` or `draft` |
| `WORDPRESS_CATEGORY_ID` | `0` | Category ID. `0` omits the field |
| `CTA_URL` | `https://oykomed.it` | Target of the closing call to action in every issue |
| `BASE_URL` | `http://localhost:8000` | Public URL for confirmation/unsubscribe links |
| `HEALTHCHECK_PING_URL` | (empty) | URL to GET after a successful pipeline run (Healthchecks.io, Uptime Kuma) |
| `PREVIEW_MODE` | `false` | If `true`, always hold the issue in review rather than sending |
| `LOG_LEVEL` | `INFO` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## Local Development Setup

```bash
# Clone and enter the project
cd Oykos-Newsletter

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Linux/macOS)
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy and edit configuration
cp .env.example .env
# Edit .env with your values

# Run tests
pytest tests/ -v

# Verify the external boundaries before the first real run
oykos check-smtp
oykos check-sources

# Run the daily ingestion
oykos ingest

# Start the web server
oykos serve
```

---

## Database Setup

### Option A: SQLite (local dev only)

```env
DATABASE_URL=sqlite+aiosqlite:///oykos.db
```

Tables are auto-created on first pipeline run. No migration step needed for fresh installs.

### Option B: PostgreSQL (recommended for production)

```env
DATABASE_URL=postgresql+asyncpg://oykos:your-password@localhost:5432/oykos
```

**Initial setup:**

```bash
# Create database
createdb oykos

# Run Alembic migrations
alembic upgrade head
```

**Creating new migrations** (after changing `src/oykos/db/tables.py`):

```bash
alembic revision --autogenerate -m "describe_the_change"
alembic upgrade head
```

### Adapting the Database

The system uses **SQLAlchemy 2.0 async** with these drivers:

| Database | Driver | Connection String |
|----------|--------|-------------------|
| PostgreSQL | `asyncpg` | `postgresql+asyncpg://user:pass@host:5432/db` |
| SQLite | `aiosqlite` | `sqlite+aiosqlite:///path/to/file.db` |
| MySQL | `aiomysql` | `mysql+aiomysql://user:pass@host:3306/db` |
| SQL Server | `aioodbc` | `mssql+aioodbc://user:pass@host/db?driver=ODBC+Driver+18` |

To use a different database:
1. Install the appropriate async driver (`pip install aiomysql`, etc.)
2. Update `DATABASE_URL` in `.env`
3. No code changes are needed - SQLAlchemy handles dialect differences

**Tables created:**
- `news_items` - Ingested articles with classification, scoring, gating, editorial
- `newsletters` - Rendered issues with HTML content, `public_url` and status
- `review_decisions` - Human review audit trail
- `subscribers` - Email subscribers with double opt-in tokens and preferences
- `feedback` - Reader feedback ratings and structured signals per issue
- `alerts` - Trigger alert ledger, used to enforce the monthly cap

---

## OpenAI / LLM Configuration

The system uses the standard **OpenAI Python SDK** (`openai >= 1.82`). It works with:

### Standard OpenAI

```env
OPENAI_API_KEY=sk-proj-your-key
OPENAI_MODEL=gpt-5.4
OPENAI_TRIAGE_MODEL=gpt-5-mini
```

### Where the money goes

The two model settings are not interchangeable knobs - the split is deliberate:

| Task | Model | Calls per week |
|------|-------|----------------|
| Classification + 7 subscores | `OPENAI_TRIAGE_MODEL` | one per ingested item, capped at 60 per daily run |
| Evidence extraction, synthesis, verification | `OPENAI_MODEL` | one set per **shortlisted** item only (`MAX_NEWSLETTER_ITEMS + 3`) |
| Subject line + preheader | `OPENAI_TRIAGE_MODEL` | one per issue |

The weekly pipeline gates and ranks *before* it writes any copy, so the primary
model never runs on an item that has not already earned a slot. Pointing
`OPENAI_MODEL` at a cheaper tier is the single biggest lever on cost, and needs
no code change.

### Azure OpenAI

If your infrastructure uses Azure OpenAI, you need to swap the client in
`src/oykos/llm/client.py`. Change `AsyncOpenAI` to `AsyncAzureOpenAI`:

```python
# In src/oykos/llm/client.py, replace:
from openai import AsyncOpenAI
# ...
self._client = AsyncOpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    base_url=settings.openai_base_url,
    timeout=settings.openai_timeout_seconds,
    max_retries=settings.openai_max_retries,
)

# With:
from openai import AsyncAzureOpenAI
# ...
self._client = AsyncAzureOpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    azure_endpoint="https://your-resource.openai.azure.com",
    api_version="2024-12-01-preview",
    timeout=settings.openai_timeout_seconds,
    max_retries=settings.openai_max_retries,
)
```

And add the Azure-specific env vars to `config.py` and `.env`. The deployment
must expose the Responses API, since every structured call goes through it.

### OpenAI-compatible providers (Ollama, LM Studio, vLLM, etc.)

Override the base URL to point to your local/custom endpoint:

```env
OPENAI_API_KEY=not-needed          # Some providers don't require a key
OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama example
OPENAI_MODEL=llama3.1:70b
OPENAI_TRIAGE_MODEL=llama3.1:8b
```

The endpoint must implement the OpenAI **Responses** API (`/responses`) with
strict JSON schema output, not just Chat Completions - `LLMClient` calls
`responses.create` and `responses.parse` for every request. Verify that before
committing to a provider.

### Model requirements

The system relies on structured JSON output through the OpenAI **Responses API**
with Structured Outputs. Models must:
- Support the Responses API and strict JSON schema output
- Handle Italian-language content

Recommended minimum: a small modern model for triage. For editorial quality, use
the strongest model you are willing to pay for on `OPENAI_MODEL` - it only runs
on items that are going to ship.

---

## Email / SMTP Configuration

Delivery is plain SMTP through `smtplib`, so any provider works. Nothing outside
the `smtp_*` settings and `src/oykos/delivery/email_sender.py` is
provider-specific.

### Zoho Mail (default)

```env
SMTP_HOST=smtp.zoho.eu
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USERNAME=newsletter@yourdomain.it
SMTP_PASSWORD=your-app-password
SENDER_EMAIL=newsletter@yourdomain.it
```

The host must match the Zoho data centre your account lives in, and the `From`
address must be one the account owns. Both are the usual failure modes; see
[docs/deliverability.md](docs/deliverability.md) for the full table.

### Any other SMTP server

```env
# Gmail
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USE_SSL=true

# Providers that want STARTTLS (SendGrid, Mailgun, Postmark, SES)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_SSL=false
```

`connect()` picks `SMTP_SSL` for port 465 and `SMTP` + `starttls()` otherwise, so
switching provider is configuration only. The legacy `GMAIL_ADDRESS` /
`GMAIL_APP_PASSWORD` variables still resolve to `SMTP_USERNAME` /
`SMTP_PASSWORD`.

Verify before sending anything real:

```bash
oykos check-smtp
```

### Replacing the transport entirely

To move to a provider API rather than SMTP, replace these two functions in
`email_sender.py` and keep their signatures:

```python
async def send_newsletter(
    settings: Settings,
    to_emails: list[str],
    subject: str,
    html_content: str,
    text_content: str,
    list_unsubscribe_url: str = "",
) -> bool: ...

async def send_bulk(settings: Settings, messages: list[OutboundMessage]) -> int: ...
```

`send_bulk` is what the weekly pipeline uses: one rendered message per
subscriber, over a shared connection recycled every `SMTP_MAX_PER_CONNECTION`
messages and paced by `SMTP_THROTTLE_SECONDS`. It returns the number delivered.

The `list_unsubscribe_url` argument adds RFC 8058 one-click unsubscribe headers,
which Gmail and Outlook require for bulk senders. Keep it.

---

## WordPress Publishing

Each issue is POSTed to the WordPress REST API **before** the email goes out, so
the email footer can link to a live "Leggi online" page.

```env
WORDPRESS_URL=https://oykomed.it
WORDPRESS_USER=your-wp-username
WORDPRESS_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WORDPRESS_STATUS=publish
WORDPRESS_CATEGORY_ID=0
```

- Endpoint: `POST {WORDPRESS_URL}/wp-json/wp/v2/posts`, core WordPress, no
  plugin required.
- Auth: HTTP Basic with a WordPress **Application Password** (Users > Profile >
  Application Passwords, WordPress 5.6+, HTTPS required). This is not the
  account password.
- The returned post URL is stored on `Newsletter.public_url` and the `public_url`
  column of `newsletters`.
- Publishing is enabled only when URL, user and password are all set. Leave
  `WORDPRESS_URL` empty and the step is skipped; email delivery is unaffected.
- A failure is logged and returns an empty string. Delivery proceeds without the
  online link - publishing never blocks the send.

Full setup and troubleshooting: [docs/wordpress.md](docs/wordpress.md).

---

## Docker Deployment

### Quick start with Docker Compose

```bash
# Start PostgreSQL + web server
docker compose up -d db web

# Run migrations (first time)
docker compose --profile setup run --rm migrate

# Daily ingestion
docker compose --profile cron run --rm pipeline

# Weekly composition (lands in the review queue)
docker compose --profile cron run --rm compose-issue

# Deliver approved issues
docker compose --profile cron run --rm send
```

### Services

| Service | Purpose | Profile | Port |
|---------|---------|---------|------|
| `db` | PostgreSQL 16 | - | 5432 |
| `web` | FastAPI server (subscribers, archive, feedback, review) | - | 8000 |
| `pipeline` | `oykos ingest` - daily ingestion | `cron` | - |
| `compose-issue` | `oykos compose` - weekly composition | `cron` | - |
| `send` | `oykos send` - deliver approved issues | `cron` | - |
| `migrate` | Alembic migration runner | `setup` | - |

### Scheduling

The three job services run on demand. Schedule them with whatever the host
provides - there is no workflow engine to deploy.

**Linux cron:**
```cron
# Daily ingestion, Mon-Fri at 06:00
0 6 * * 1-5 cd /path/to/project && docker compose --profile cron run --rm pipeline

# Weekly composition, Friday at 07:00
0 7 * * 5 cd /path/to/project && docker compose --profile cron run --rm compose-issue

# Delivery sweep, hourly - picks up whatever an editor approved
0 * * * * cd /path/to/project && docker compose --profile cron run --rm send
```

**systemd timers, AWS EventBridge, GitHub Actions schedule**, etc. all work.

### Custom Docker builds

The Dockerfile uses `python:3.12-slim`. Adjust as needed:

```dockerfile
# For different Python version:
FROM python:3.13-slim AS base

# For Alpine (smaller image, may need build deps):
FROM python:3.12-alpine AS base
RUN apk add --no-cache libpq
```

---

## Running the Pipeline

### CLI commands

```bash
# Daily, Mon-Fri: ingest, classify, score, gate, evaluate alerts
oykos ingest

# Weekly: rank, shortlist, synthesise, verify, compose. Lands in review.
oykos compose

# Publish approved issues to WordPress and deliver them
oykos send

# Ingest then compose, in order
oykos run

# Always hold the issue for review, whatever REVIEW_TOKEN says
oykos run --preview

# Web server
oykos serve --host 0.0.0.0 --port 8000

# Preflight checks
oykos check-smtp        # connect, authenticate, probe the From address
oykos check-sources     # fetch every enabled source, print OK/DEAD + counts

# Version
oykos --version
```

### Pipeline phases

**Daily (`oykos ingest`)**

1. **Ingest** - Fetch RSS and scraped sources, normalize URLs, dedup against DB
2. **Classify + score** - Triage model produces taxonomy and 7 subscores;
   weighted score, transferability and penalties applied
3. **Gate** - Three selection gates plus exclusion criteria
4. **Alerts** - Evaluate the four hard trigger categories, under the monthly cap

**Weekly (`oykos compose`)**

5. **Gather candidates** - Unsent items above threshold, topped up from the
   7-28 day backlog if sparse
6. **Rank** - Section quotas and hard Italy/foreign caps produce a shortlist of
   `MAX_NEWSLETTER_ITEMS + 3`
7. **Synthesize + verify** - Primary model, shortlist only. Ungrounded items are
   blocked, not published
8. **Compose + render** - Slots, TL;DR, reading time, subject line, HTML and
   plain text with the closing CTA
9. **Review gate** - Issue saved as `IN_REVIEW`; every item needs sign-off

**On approval (`oykos send`)**

10. **Publish** - POST to WordPress, store `public_url`
11. **Send** - One message per subscriber, then mark items sent
12. **Healthcheck** - Ping `HEALTHCHECK_PING_URL` on success

### Review workflow

```bash
# 1. Generate and set a review token
python -c "import secrets; print(secrets.token_urlsafe(32))"   # -> REVIEW_TOKEN

# 2. Compose the issue
oykos compose

# 3. Open http://localhost:8000/review, sign in, decide on every item

# 4. Either click "Approva e invia ora", or approve and let the sweep pick it up
oykos send
```

With `REVIEW_TOKEN` unset the review router returns 404 for every path and
issues will simply pile up in `IN_REVIEW` with nothing able to approve them.
Set it before the first real run.

---

## Web Server

The FastAPI web server handles subscriber management, the public archive,
feedback and the editorial review workbench:

```bash
oykos serve --host 0.0.0.0 --port 8000
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Public landing page and signup form |
| GET | `/health` | Healthcheck |
| POST | `/api/subscribe` | Register new subscriber (JSON) |
| POST | `/subscribe` | Register new subscriber (HTML form, no JS) |
| GET | `/confirm/{token}` | Double opt-in confirmation |
| GET | `/preferences/{token}` | Per-subscriber preferences page |
| POST | `/preferences/{token}` | Save topics, alert opt-in, region |
| GET | `/unsubscribe/{token}` | Show unsubscribe page |
| POST | `/unsubscribe/{token}` | Process unsubscribe (RFC 8058 one-click) |
| POST | `/api/erase` | GDPR right to erasure |
| GET | `/feedback/{issue_id}` | Feedback form page |
| POST | `/api/feedback` | Submit issue feedback (1-5 rating) |
| POST | `/feedback/{issue_id}` | Submit feedback (HTML form) |
| GET | `/archive` | Public archive: list of sent issues |
| GET | `/archive/{week}` | View a past issue |
| GET | `/review` | Editorial review queue (requires `REVIEW_TOKEN`) |
| GET | `/review/{week}` | Per-issue review workbench |

The archive lists issues newest first; there is no full-text search parameter.
All `/review` paths return 404 when `REVIEW_TOKEN` is unset.

### Reverse proxy

In production, put the web server behind nginx / Caddy / your load balancer:

```nginx
server {
    listen 443 ssl;
    server_name newsletter.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Set `BASE_URL=https://newsletter.yourdomain.com` so confirmation/unsubscribe links
point to the correct domain.

---

## CI/CD

A GitHub Actions workflow is included at `.github/workflows/ci.yml`:

- Runs on push to `main` and pull requests
- Tests on Python 3.12 and 3.13
- Lint + format check with ruff
- Full test suite with pytest

To adapt for **GitLab CI**, **Azure DevOps**, or **Jenkins**, the key steps are:

```bash
pip install -e ".[dev]"
ruff check src/ tests/
ruff format --check src/ tests/
pytest tests/ -v --tb=short
```

Required CI env vars:
```
DATABASE_URL=sqlite+aiosqlite:///test.db
OPENAI_API_KEY=test-key
GMAIL_ADDRESS=test@test.com
GMAIL_APP_PASSWORD=test-password
```

(`GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` are the legacy aliases for
`SMTP_USERNAME` / `SMTP_PASSWORD`; either spelling works.)

The local gate is stricter than CI - `scripts/vibe-check.ps1` also runs pyright
in strict mode and enforces the 65% coverage floor:

```powershell
.\scripts\vibe-check.ps1
```

---

## Adapting to Your Infrastructure

### Checklist for production deployment

- [ ] Set `DATABASE_URL` to your PostgreSQL instance
- [ ] Set `OPENAI_API_KEY` (or configure your LLM provider via `OPENAI_BASE_URL`)
- [ ] Configure SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SENDER_EMAIL`)
- [ ] Set `BASE_URL` to your public-facing domain
- [ ] **Set `REVIEW_TOKEN`** - without it nobody can approve an issue and nothing ever sends
- [ ] Publish SPF, DKIM and DMARC on the sending domain (docs/deliverability.md)
- [ ] Run `alembic upgrade head` for database migrations
- [ ] Run `oykos check-smtp` and `oykos check-sources` before the first real run
- [ ] Schedule `oykos ingest` (daily), `oykos compose` (weekly), `oykos send` (often)
- [ ] (Optional) Configure WordPress publishing; start with `WORDPRESS_STATUS=draft`
- [ ] (Optional) Set `CTA_URL` to your own landing page
- [ ] (Optional) Set `HEALTHCHECK_PING_URL` for monitoring
- [ ] (Optional) Put the web server behind a reverse proxy with TLS

### Swapping the LLM provider

The only file to touch is `src/oykos/llm/client.py`. The `LLMClient` class wraps
all LLM calls. For an OpenAI-compatible endpoint you do not even need that -
`OPENAI_BASE_URL`, `OPENAI_MODEL` and `OPENAI_TRIAGE_MODEL` cover it. See
[OpenAI / LLM Configuration](#openai--llm-configuration) above.

### Swapping the email provider

Configuration first: `SMTP_HOST`, `SMTP_PORT` and `SMTP_USE_SSL` handle any SMTP
server. Only an API-based provider requires touching
`src/oykos/delivery/email_sender.py`; keep the `send_newsletter` and `send_bulk`
signatures.

### Publishing somewhere other than WordPress

Replace `publish_issue` in `src/oykos/delivery/wordpress.py`. It takes
`(Settings, Newsletter)` and returns the public URL, or an empty string on
failure. Nothing else in the pipeline knows about WordPress.

### Adding sources

Edit `src/oykos/models/source.py` and add a `Source` entry: key, name, URL,
`source_type`, `tier`, `reliability` (0-5), country and optional
`category_hints`. Update `docs/sources.md` to match, then confirm the feed is
alive with `oykos check-sources`.

### Customizing the newsletter template

Edit `src/oykos/newsletter/template.py`. The HTML template is a Jinja2 string
with responsive email CSS, autoescaped. The closing CTA copy lives in the
`CTA_TITLE`, `CTA_SUBTITLE` and `CTA_BUTTON` constants at the top of the module;
its destination is the `CTA_URL` setting. The plain text fallback is built by
`render_plain_text` in the same file and must stay in sync.

---

## Troubleshooting

### "No candidates available" error

The pipeline found no news items to include. Check:
- Sources are reachable from your network: `oykos check-sources`
- Items score above the minimum threshold (30.0 fresh, 20.0 backlog)
- `MAX_NEWSLETTER_ITEMS` is not set to 0

### The issue never sends

An issue sits in `IN_REVIEW` until a human decides on **every** item. Check:
- `REVIEW_TOKEN` is set. If it is empty the review UI 404s and nothing can ever
  be approved
- `PREVIEW_MODE` is not `true`
- `oykos send` is actually scheduled - approval alone does not deliver unless you
  used "Approva e invia ora"

### "Newsletter has 0 slots after gating"

Every candidate failed the selection gates or was blocked by verification.
Common causes: a run where classification failed (check the logs for
"Classification failed"), or a week with only low-trust sources returning items.

### SMTP connection timeout

- Run `oykos check-smtp` first; it reports the specific failure and what to change
- Port 465 is implicit SSL, port 587 is STARTTLS. Set `SMTP_USE_SSL` to match
- If your infrastructure blocks 465, switch to `SMTP_PORT=587` and
  `SMTP_USE_SSL=false`
- Zoho: confirm the host matches your data centre and that your plan includes
  SMTP access

### WordPress publishing returns 401

You are almost certainly using the account password. Generate an Application
Password at Users > Profile > Application Passwords (HTTPS required). See
[docs/wordpress.md](docs/wordpress.md) for the full table of failure modes.
Publishing failures never block the email, so the symptom is a missing
"Leggi online" link plus an error in the logs.

### OpenAI API errors

- Verify `OPENAI_API_KEY` is valid and has credits
- If using a custom `OPENAI_BASE_URL`, verify the endpoint implements the
  Responses API with Structured Outputs
- Check `OPENAI_MODEL` and `OPENAI_TRIAGE_MODEL` match models available at your
  endpoint

### Database migration errors

```bash
# Check current migration state
alembic current

# Generate a new migration if tables changed
alembic revision --autogenerate -m "description"

# Apply
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

### Tests fail with missing env vars

Tests require these env vars (any dummy value works):
```
DATABASE_URL=sqlite+aiosqlite:///test.db
OPENAI_API_KEY=test-key
GMAIL_ADDRESS=test@test.com
GMAIL_APP_PASSWORD=test-password
```
