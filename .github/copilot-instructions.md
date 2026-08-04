# Copilot Instructions - Oykos Newsletter Engine

## Project
Italian Pediatrics Newsletter Engine for PLS (Pediatricians of Free Choice). Deterministic pipeline with LLM in the loop.

## Tech Stack
- Python 3.12+, strict typing everywhere
- Pydantic v2 for all data models (strict mode)
- SQLAlchemy 2.0 (async) + Alembic for database
- PostgreSQL for production, SQLite for local dev/tests. No pgvector
- OpenAI Responses API + Structured Outputs (GPT-5.4 primary, GPT-5 mini for triage)
- httpx for HTTP (async, with timeouts)
- feedparser for RSS/Atom, BeautifulSoup for the controlled scraper
- Orchestration is plain async functions in `src/oykos/pipeline/`, driven by the
  CLI and cron. There is no workflow engine - do not add Prefect, Airflow or
  Celery without an ADR
- FastAPI + Jinja2 for the subscriber pages and review UI
- SMTP via `smtplib` for email delivery (Zoho by default, any server works)
- WordPress REST API for publishing each issue before the send
- pytest + pytest-asyncio for testing
- ruff for linting, pyright (strict) for type checking

## Conventions
- Source code lives in `src/oykos/`
- Tests mirror source structure in `tests/unit/`, `tests/integration/`, `tests/e2e/`
- All config via `pydantic-settings`, secrets via environment variables only
- No hardcoded values - URLs, keys, paths, magic numbers go in config
- Every new function needs a type signature and a test
- Use `from __future__ import annotations` in every module
- Prefer `pathlib.Path` over `os.path`
- Use `httpx.AsyncClient` with explicit timeouts (never unlimited)
- All database operations through repository layer (`src/oykos/db/repository.py`)
- LLM calls always use Structured Outputs with Pydantic response schemas
- Every LLM output must include citations back to source content

## Before Writing Code
- Search `src/oykos/` for existing utilities. Prefer extension over duplication
- Read `.vibe/STATE.md` and recent session logs before proposing code
- Check `docs/data-model.md` before creating/modifying any Pydantic model
- Check `docs/scoring.md` before touching scoring logic
- Check `docs/sources.md` before adding/modifying source connectors
- Check `docs/deviations.md` before proposing a feature that sounds like it is
  in the PRD. Nine blueprint features were deliberately cut; `docs/PRD.md` and
  `docs/strategy.md` describe intent, not the build

## Stop Directive
If you are unsure whether a function, method, or API exists in a dependency, STOP and say "I'm not sure this API exists - please verify." Do not invent plausible-looking function signatures.

## Test Requirements
- Failing tests first, always. Non-negotiable.
- Use fixtures in `tests/fixtures/` for sample data
- Mock external services (OpenAI, RSS feeds, email ESP) in unit tests
- Integration tests use real DB (test container or SQLite)
- Coverage target: >= 90% for AI-generated code
- Test behavior, not implementation details

## Security
- No PII in LLM prompts (no email addresses, no subscriber names)
- HTML output must escape all user/source content (prevent XSS)
- SQL via SQLAlchemy ORM only (no raw string queries)
- Validate all external input at system boundaries
- Secrets only from environment, never committed

## Current State
See `.vibe/STATE.md` for project state and `.vibe/backlog.md` for slice list.

## Formatting
- Never use em-dashes or en-dashes - use hyphens instead
- Italian copy MUST carry its accents: attività, perché, più, già, ciò, età,
  priorità, affidabilità, né, è. The audience is Italian physicians and
  unaccented Italian reads as misspelled. Subject headers are auto-encoded to
  RFC 2047 and both MIME parts are utf-8, so accents are safe end to end.
- Conventional commits: `feat(scope): description (spec: SXXX)`
