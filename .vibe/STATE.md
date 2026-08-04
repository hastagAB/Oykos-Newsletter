# State

## Now
Post-1.1.0 scope cut plus three additions, unreleased. Nine blueprint features
removed as premature (see `docs/deviations.md`); WordPress publishing, a closing
CTA and three research/AI sources added. Daily ingestion, weekly composition,
full human review, publish-then-send delivery.

`oykos --version` and `web/app.py` still report 1.1.0. Bump both when this is
tagged.

## Last working state
2026-07-28: quality gate green - ruff clean, pyright strict clean, 132 tests
passing, 76% coverage. Alembic baseline verified up and down.

The gate has NOT been re-run since the cut. The tree now holds 139 test
functions (143 collected: `test_digest_material_never_triggers_an_alert` is
parametrised into 5 cases). Run `.\scripts\vibe-check.ps1` before trusting any
number above.

## Active constraints
- Python 3.12+, strict typing (Pydantic v2)
- OpenAI Responses API with Structured Outputs; GPT-5.4 synthesis, GPT-5 mini
  triage. Provider swappable via `OPENAI_BASE_URL` with no code change
- SQLite (aiosqlite) for local dev, PostgreSQL ready for production. No pgvector
- SMTP delivery, Zoho by default; Bcc for multi-recipient sends
- Weekly digest for Italian PLS; trigger alerts capped at 2 per rolling 30 days
- 12 slots: Top 3 + Clinical 2-3 + Regulatory 1-2 + Device 1-2 + CME 1-2
- 8 Italian / 4 foreign, hard caps. A thin week ships a shorter issue
- Every item passes 3 gates: PLS relevance, reliability, actionability
- Preprints and low-trust items are excluded, never demoted
- Every published claim is grounded in a verbatim source passage
- Every item in an issue requires human sign-off. No sampling, no auto-approval
- REVIEW_TOKEN must be set or the review interface refuses to serve
- Ranking runs before synthesis: the primary model never writes copy for an item
  that has not earned a slot
- The issue is published to WordPress before the email goes out, so
  "Leggi online" resolves on arrival

## Deliberately not built
See `docs/deviations.md` for the full record - what the blueprint asked for,
what ships instead, why it was cut, and the trigger that would reopen it.

Summary: Radar section, Decision Cards, A/B subject testing, semantic dedup,
referrals, archive search, Prefect, PDF ingestion, the eval harness, the
auto-approval review policy, geo-cap relaxation.

Also not built, and not on the blueprint's critical path:
- Personalised issue content per subscriber. Preferences are collected but the
  composer still produces one issue for everyone.
- Learning-to-rank re-weighting (blueprint 90-day item).
- Agenas ECM API. Scraped instead, because the API contract is not documented.

## Do not touch without ADR
- Data model schema (docs/data-model.md)
- Scoring weights and hard rules (docs/scoring.md)
- Source whitelist tiers (docs/sources.md)
- The two title-similarity thresholds (0.85 drop / 0.75 penalty) and why they
  differ (docs/scoring.md)
- Publish-before-send ordering in `weekly.deliver_and_finalize`
