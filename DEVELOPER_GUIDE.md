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
8. [Docker Deployment](#docker-deployment)
9. [Running the Pipeline](#running-the-pipeline)
10. [Web Server (Subscribers, Archive, Feedback)](#web-server)
11. [CI/CD](#cicd)
12. [Adapting to Your Infrastructure](#adapting-to-your-infrastructure)
13. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
                  +------------------+
                  |   RSS Sources    |
                  |  (40+ Italian &  |
                  |   int'l feeds)   |
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
              2. Classify + Score (OpenAI)
              3. Synthesize Editorial (OpenAI)
              4. Compose + Render HTML
                           |
                  +--------v---------+
                  |  Email Delivery  |
                  |  (SMTP / per-    |
                  |   subscriber)    |
                  +------------------+
                           |
                  +--------v---------+
                  | FastAPI Web App  |
                  |  /subscribe      |
                  |  /confirm/{tok}  |
                  |  /unsubscribe    |
                  |  /archive        |
                  |  /feedback       |
                  +------------------+
```

**Key components:**

| Module | Purpose |
|--------|---------|
| `oykos.ingestion` | RSS fetching, HTML cleaning, URL normalization, deduplication |
| `oykos.llm` | OpenAI client, classification, editorial synthesis, claim verification |
| `oykos.processing` | 7-dimension scoring engine, candidate ranking |
| `oykos.newsletter` | Composition (section layout, IT/foreign ratio), Jinja2 rendering, subject line A/B generation |
| `oykos.delivery` | Gmail SMTP sender, FastAPI review API |
| `oykos.web` | Subscriber management, public archive, feedback micro-survey |
| `oykos.db` | SQLAlchemy async ORM, repositories, Alembic migrations |
| `oykos.pipeline` | Full daily pipeline orchestrator (9 phases) |

---

## Prerequisites

- **Python** >= 3.12
- **PostgreSQL** >= 14 (production) or SQLite (local dev)
- **OpenAI API key** (or any OpenAI-compatible endpoint)
- **SMTP credentials** (Gmail app password or your own SMTP server)

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
| `GMAIL_ADDRESS` | SMTP sender email | `newsletter@yourdomain.com` |
| `GMAIL_APP_PASSWORD` | SMTP password (Gmail: generate at myaccount.google.com/apppasswords) | `xxxx xxxx xxxx xxxx` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Override for OpenAI-compatible providers (see [LLM section](#openai--llm-configuration)) |
| `OPENAI_MODEL` | `gpt-4o` | Primary model for editorial synthesis |
| `OPENAI_TRIAGE_MODEL` | `gpt-4o-mini` | Cheaper model for classification tasks |
| `SENDER_EMAIL` | (same as `GMAIL_ADDRESS`) | "From" address in outgoing emails |
| `RECIPIENT_EMAILS` | (empty) | Legacy comma-separated recipient list (use subscriber table instead) |
| `NEWSLETTER_TITLE` | `L'Essenziale in Pediatria` | Title shown in emails and archive |
| `MAX_NEWSLETTER_ITEMS` | `12` | Maximum items per issue |
| `ITALY_RATIO` | `0.7` | Target Italy/foreign news ratio (0.0 - 1.0) |
| `BASE_URL` | `http://localhost:8000` | Public URL for confirmation/unsubscribe links |
| `HEALTHCHECK_PING_URL` | (empty) | URL to GET after successful pipeline run (e.g., Healthchecks.io, Uptime Kuma) |
| `AB_TEST_PERCENT` | `10` | % of subscribers receiving subject line variant B (0 - 50) |
| `PREVIEW_MODE` | `false` | If `true`, pipeline saves newsletter without sending; requires manual approval |
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

# Run the pipeline
oykos

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
- `news_items` - Ingested articles with classification, scoring, editorial
- `newsletters` - Rendered issues with HTML content and status
- `review_decisions` - Human review audit trail
- `subscribers` - Email subscribers with double opt-in tokens
- `feedback` - Reader feedback ratings per issue

---

## OpenAI / LLM Configuration

The system uses the standard **OpenAI Python SDK** (`openai >= 1.82`). It works with:

### Standard OpenAI

```env
OPENAI_API_KEY=sk-proj-your-key
OPENAI_MODEL=gpt-4o
OPENAI_TRIAGE_MODEL=gpt-4o-mini
```

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
)

# With:
from openai import AsyncAzureOpenAI
# ...
self._client = AsyncAzureOpenAI(
    api_key=settings.openai_api_key.get_secret_value(),
    azure_endpoint="https://your-resource.openai.azure.com",
    api_version="2024-12-01-preview",
)
```

And add the Azure-specific env vars to `config.py` and `.env`.

### OpenAI-compatible providers (Ollama, LM Studio, vLLM, etc.)

Override the base URL to point to your local/custom endpoint:

```env
OPENAI_API_KEY=not-needed          # Some providers don't require a key
OPENAI_BASE_URL=http://localhost:11434/v1   # Ollama example
OPENAI_MODEL=llama3.1:70b
OPENAI_TRIAGE_MODEL=llama3.1:8b
```

Any provider that implements the OpenAI Chat Completions API works out of the box.

### Model requirements

The system relies on structured JSON output. Models must:
- Follow JSON schema instructions reliably
- Handle Italian-language content
- Support `max_completion_tokens` parameter (all modern OpenAI SDK models do)

Recommended minimum: `gpt-4o-mini` or equivalent. For best editorial quality: `gpt-4o`.

---

## Email / SMTP Configuration

### Gmail (default)

```env
GMAIL_ADDRESS=newsletter@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

Generate an app password at: https://myaccount.google.com/apppasswords

The system uses `SMTP_SSL` on port 465.

### Custom SMTP Server

To use a different SMTP provider, modify `src/oykos/delivery/email_sender.py`:

```python
# Current (Gmail SMTP_SSL):
GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465

# For STARTTLS providers (e.g., SendGrid, Mailgun):
# Change smtplib.SMTP_SSL to smtplib.SMTP and add .starttls()
```

You can also replace the entire email delivery with **SendGrid**, **AWS SES**, or
**Mailgun** by swapping the `send_newsletter()` function. The function signature is:

```python
async def send_newsletter(
    settings: Settings,
    to_emails: list[str],
    subject: str,
    html_content: str,
    text_content: str,
    list_unsubscribe_url: str = "",
) -> bool:
```

The `list_unsubscribe_url` parameter adds RFC 8058 one-click unsubscribe headers,
which Gmail and Outlook require for bulk senders.

---

## Docker Deployment

### Quick start with Docker Compose

```bash
# Start PostgreSQL + web server
docker compose up -d db web

# Run migrations (first time)
docker compose run --rm --profile setup migrate

# Run the pipeline manually
docker compose run --rm --profile cron pipeline
```

### Services

| Service | Purpose | Port |
|---------|---------|------|
| `db` | PostgreSQL 16 | 5432 |
| `web` | FastAPI server (subscribers, archive, feedback) | 8000 |
| `pipeline` | Daily newsletter pipeline (on-demand via `docker compose run`) | - |
| `migrate` | Alembic migration runner | - |

### Scheduling the pipeline

The `pipeline` service is in the `cron` profile and runs on-demand. Schedule it with
your preferred scheduler:

**Linux cron:**
```cron
0 6 * * 1 cd /path/to/project && docker compose run --rm --profile cron pipeline
```

**systemd timer, AWS EventBridge, GitHub Actions schedule**, etc. all work.

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
# Full pipeline (ingest -> classify -> score -> compose -> send)
oykos

# Preview mode (saves newsletter without sending)
oykos --preview

# Start web server
oykos serve --host 0.0.0.0 --port 8000

# Version
oykos --version
```

### Pipeline phases

1. **Ingest** - Fetch RSS feeds, normalize URLs, dedup against DB
2. **Classify + Score** - LLM classification, 7-dimension scoring
3. **Gather candidates** - Pull unsent items + backlog
4. **Synthesize editorial** - LLM generates headline, "why it matters", action items
5. **Compose** - Section sorting, IT/foreign ratio enforcement
6. **Render** - Jinja2 HTML + plain text, A/B subject line generation
7. **Preview gate** (optional) - Pause for human review
8. **Send** - Per-subscriber emails with unsubscribe headers, A/B split
9. **Healthcheck** - Ping monitoring URL on success

### Preview mode workflow

```bash
# 1. Run pipeline in preview mode
oykos --preview

# 2. Review the newsletter at http://localhost:8000/api/newsletters/{week}
# 3. Approve via the review API
# 4. Run again without --preview to send
```

---

## Web Server

The FastAPI web server handles subscriber management, public archive, and feedback:

```bash
oykos serve --host 0.0.0.0 --port 8000
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Healthcheck |
| POST | `/api/subscribe` | Register new subscriber |
| GET | `/confirm/{token}` | Double opt-in confirmation |
| GET | `/unsubscribe/{token}` | Show unsubscribe page |
| POST | `/unsubscribe/{token}` | Process unsubscribe (RFC 8058) |
| POST | `/api/erase` | GDPR right to erasure |
| POST | `/api/feedback` | Submit issue feedback (1-5 rating) |
| GET | `/feedback/{issue_id}` | Feedback form page |
| GET | `/archive` | Public newsletter archive |
| GET | `/archive/{week}` | View a past newsletter |
| GET | `/refer/{code}` | Referral landing page |

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

---

## Adapting to Your Infrastructure

### Checklist for production deployment

- [ ] Set `DATABASE_URL` to your PostgreSQL instance
- [ ] Set `OPENAI_API_KEY` (or configure your LLM provider via `OPENAI_BASE_URL`)
- [ ] Configure SMTP credentials (`GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`) or replace `email_sender.py`
- [ ] Set `BASE_URL` to your public-facing domain
- [ ] Run `alembic upgrade head` for database migrations
- [ ] Set `PREVIEW_MODE=true` for initial runs to verify content quality
- [ ] Configure a cron job or scheduler for `oykos` command
- [ ] (Optional) Set `HEALTHCHECK_PING_URL` for monitoring
- [ ] (Optional) Put the web server behind a reverse proxy with TLS

### Swapping the LLM provider

The only file to touch is `src/oykos/llm/client.py`. The `LLMClient` class wraps
all LLM calls. Swap the client initialization and the rest of the codebase works
unchanged. See [OpenAI / LLM Configuration](#openai--llm-configuration) above.

### Swapping the email provider

The only file to touch is `src/oykos/delivery/email_sender.py`. Replace the
`send_newsletter()` function body. Keep the same function signature and return
`True` on success, `False` on failure.

### Adding RSS sources

Edit `src/oykos/models/source.py` to add or remove news sources. Each source
has a name, URL, tier (IT/EU/global), and reliability score.

### Customizing the newsletter template

Edit `src/oykos/newsletter/template.py`. The HTML template is a Jinja2 string
with responsive email CSS. The plain text fallback is auto-generated.

---

## Troubleshooting

### "No candidates available" error

The pipeline found no news items to include. Check:
- RSS sources are reachable from your network
- Items score above the minimum threshold (30.0)
- `MAX_NEWSLETTER_ITEMS` is not set to 0

### SMTP connection timeout

- Gmail uses SMTP_SSL on port 465. Ensure outbound port 465 is open.
- If your infrastructure blocks port 465, switch to STARTTLS on port 587 in `email_sender.py`.
- For corporate SMTP, update the host/port/auth in the sender module.

### OpenAI API errors

- Verify `OPENAI_API_KEY` is valid and has credits
- If using a custom `OPENAI_BASE_URL`, verify the endpoint serves the Chat Completions API
- Check `OPENAI_MODEL` matches an available model at your endpoint

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
