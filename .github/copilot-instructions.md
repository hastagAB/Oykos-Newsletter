# Copilot Instructions - Oykos Newsletter Engine

## Project
Italian Pediatrics Newsletter Engine for PLS (Pediatricians of Free Choice). Deterministic pipeline with LLM in the loop.

## Tech Stack
- Python 3.12+, strict typing everywhere
- Pydantic v2 for all data models (strict mode)
- SQLAlchemy 2.0 (async) + Alembic for database
- PostgreSQL + pgvector (SQLite for local dev/tests)
- OpenAI Responses API + Structured Outputs (GPT-5.4 primary, GPT-5 mini for triage)
- httpx for HTTP (async, with timeouts)
- feedparser for RSS/Atom
- Prefect for orchestration
- FastAPI + Jinja2 for review UI
- SendGrid for email delivery
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
- Read `STATE.md` and recent session logs before proposing code
- Check `docs/data-model.md` before creating/modifying any Pydantic model
- Check `docs/scoring.md` before touching scoring logic
- Check `docs/sources.md` before adding/modifying source connectors

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
- Conventional commits: `feat(scope): description (spec: SXXX)`
