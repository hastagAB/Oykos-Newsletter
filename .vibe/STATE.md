# State

## Now
v1.0.0 - Full pipeline operational. Daily newsletter running with DB persistence,
dedup, backlog fallback, and Gmail SMTP delivery.

## Last working state
Pipeline test run completed 2026-04-29: 147 articles ingested from 12 sources,
40 classified/scored, 15 editorials synthesized, 8-item newsletter composed and
sent via Gmail SMTP. All 127 tests pass.

## Active constraints
- Python 3.12+, strict typing (Pydantic v2)
- Azure OpenAI GPT-5.2 via AsyncAzureOpenAI (use max_completion_tokens, not max_tokens)
- SQLite (aiosqlite) for local dev, PostgreSQL ready for production
- Gmail SMTP_SSL (port 465) with app password for email delivery
- Weekly newsletter for Italian PLS (pediatricians of free choice)
- 70/30 Italy/abroad ratio enforced on final slots
- Every item passes 3 gates: PLS relevance, reliability, actionability
- 7-dimension scoring (0-100) with hard rules
- Items tracked with sent_at timestamp - never repeated across issues
- Backlog fallback: if < 5 fresh items, pull from 7-28 day unsent pool

## Known broken
- Nothing (pipeline verified end-to-end 2026-04-29)

## Do not touch without ADR
- Data model schema (docs/data-model.md)
- Scoring weights and hard rules (docs/scoring.md)
- Source whitelist tiers (docs/sources.md)
