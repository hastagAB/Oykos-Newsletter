# Changelog

All notable changes to the Oykos Newsletter Engine are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

A scope cut, not a feature release. Nine features specified in the blueprint and
built in 1.1.0 were removed because they were premature: each one added surface,
cost or risk without a reader or an operator asking for it. Three features were
added in their place, all of which someone did ask for.

`docs/deviations.md` is the new record of where the code and the blueprint
disagree, with the trigger that would justify building each cut feature.
`docs/PRD.md` and `docs/strategy.md` are unchanged and still describe the
original intent.

### Added
- WordPress publishing (`delivery/wordpress.py`). Every issue is POSTed to
  `/wp-json/wp/v2/posts` *before* the email is delivered, so the email can carry
  a working "Leggi online" link back to the site. Auth is HTTP Basic with a
  WordPress Application Password; the returned URL is stored on
  `Newsletter.public_url`. An empty `WORDPRESS_URL` disables it and a failure
  never blocks the send. Config: `WORDPRESS_URL`, `WORDPRESS_USER`,
  `WORDPRESS_APP_PASSWORD`, `WORDPRESS_STATUS`, `WORDPRESS_CATEGORY_ID`
- Closing call to action on every issue - "Inizia a risparmiare 1 ora al giorno
  nella tua attivita pediatrica" with a "Scopri Oykos" button - in both the HTML
  and the plain text rendering. Target is `CTA_URL`, default `https://oykomed.it`
- Three Tier 3 research and AI sources, all verified returning entries: Nature
  Medicine, npj Digital Medicine, Lancet Digital Health. Backed by two new
  taxonomy tags, `RESEARCH_EVIDENCE` and `AI_DIGITAL_HEALTH`; the latter routes
  an item to the Device/Test section
- `oykos check-sources`: fetches every enabled source concurrently and prints
  OK/DEAD plus item counts, exiting non-zero if nothing works. Sits next to
  `oykos check-smtp` as the second preflight check
- `docs/wordpress.md` (setup, Application Passwords, failure modes) and
  `docs/deviations.md`

### Changed
- The weekly pipeline gates and ranks **before** synthesising editorial copy.
  `run_weekly_pipeline` builds a shortlist of `max_newsletter_items +
  EDITORIAL_HEADROOM` (3) and only the shortlist reaches the primary model, so
  no budget is spent writing up items that will not ship
- Subject line generation moved from the primary model to the triage model
- Every item in an issue now requires human sign-off. The composer sets
  `needs_human_review` on all selected items and an issue cannot be approved
  until every one has a decision
- Deduplication is title similarity only: canonical URL match, then
  `SequenceMatcher` at `TITLE_SIMILARITY_THRESHOLD` (0.85) over a 28-day window
- The 70/30 Italy/foreign caps are hard. A thin week produces a shorter issue
  rather than a padded one
- Noise penalty detection moved from `processing/penalties.py` into
  `processing/scoring.detect_penalties`
- README and `docs/architecture.md` no longer claim Prefect orchestrates the
  pipeline. It never did

### Removed
- Radar section (`Section.RADAR`). Preprints and items with `source_trust <= 2`
  are now excluded by the selection gates instead of being demoted into a
  labelled section. `Tier.RADAR` is unaffected - it is a source registry tier
  for low-trust outlets and has nothing to do with the newsletter layout
- Device/POCT Decision Cards: `DecisionCard`, the `Recommendation` enum and
  `llm/decision_card.py`. Around fifteen structured clinical and economic fields
  per card, most of them absent from the source document
- A/B subject line testing: `AB_TEST_PERCENT`, `Newsletter.subject_variant` and
  the subscriber `ab_group` column. The list is nowhere near large enough for a
  weekly test to reach significance
- Embedding-based semantic deduplication: `USE_EMBEDDING_DEDUP`,
  `EMBEDDING_MODEL`, `llm/embeddings.py` and the `embedding` column. An API call
  and a stored vector per ingested item, for recall that title similarity
  already delivers on institutional republication
- Referral system: `/refer/{code}` and the `referral_code`, `referred_by` and
  `referral_count` columns. A growth loop built before retention was proven
- Archive full-text search (the `q` parameter on `/archive`). The archive still
  lists issues and still serves `/archive/{week}`
- Prefect orchestration (`pipeline/flows.py`). The pipeline is three linear
  commands with no branching; a workflow engine meant a server and a database to
  schedule three cron entries
- PDF ingestion (`ingestion/pdf.py`). Italian institutional PDFs are scanned
  images and multi-column layouts as often as extractable text, and an
  unreliable quote breaks the verbatim guard the grounding model rests on.
  `SourceType.PDF` remains in the enum, unused
- Automated evaluation harness (`observability/evaluation.py`). NDCG needs a
  labelled gold set nobody has time to build yet. The per-issue quality report
  and the `review_decisions` corrections trail remain
- Auto-approval review policy (`processing/review_policy.py`), including the 20%
  sampling path. Its only function was to let unreviewed medical content reach
  readers
- Geo-cap relaxation: `MAX_GEO_DEVIATION`, `MIN_VIABLE_TOTAL` and
  `relax_geo_caps`. The pass existed to pad an issue to a target length

## [1.1.0] - 2026-07-28

Full conformance pass against the product blueprint. See
`.vibe/decisions/ADR-001-blueprint-conformance.md` for the rationale behind the
changes to the data model, scoring and source registry.

### Added
- Editorial review workbench at `/review`: queue, per-item approve/edit/reject,
  progress tracking, and "approve and send". Access via a shared `REVIEW_TOKEN`
  exchanged for an HMAC-signed session cookie; fails closed when unset
- `review_decisions` persistence, which makes the corrections-rate KPI computable
- Controlled HTML scraper, unlocking the entire Tier-1 institutional feed
  (Ministry, AIFA, ISS, SISAC, Garante Privacy, Agenas, ECDC, EMA)
- PDF connector for guidelines, circulars and consensus documents
- Evidence snippet extraction with a verbatim guard: a quote that is not present
  in the source is discarded rather than cited
- Verification that blocks, not just downgrades: an ungrounded item, or one with
  two or more unsupported claims, never reaches a reader
- Three selection gates (PLS relevance, reliability, actionability) plus the
  exclusion criteria for generalist news, preprints and vendor marketing
- Noise penalty detection (duplicate, paywall, press release, single source)
- Device/POCT Decision Cards with the mandatory "when NOT to test" box
- Risk-based human review policy: mandatory on Top 3, prescriptive, privacy and
  device safety; stable 20% sampling elsewhere
- Radar section for low-trust and preprint items, always labelled
- Subscriber preferences page: topics, alert opt-out and region
- Structured feedback signals ("too long", "too many devices", "not relevant")
- Archive search across subject, week and body text
- Shared web design system, so every page matches the newsletter
- Optional embedding-based deduplication, Prefect flows, offline gold-set NDCG
- Alembic baseline migration, verified reversible
- End-to-end test over realistic Italian source fixtures

### Changed
- OpenAI calls use the Responses API with real Structured Outputs; the previous
  prompt-injected JSON schema and markdown-fence stripping are gone
- Default models are GPT-5.4 (synthesis) and GPT-5 mini (triage)
- `oykos` split into `ingest` (daily), `compose` (weekly), `send` and `serve`
- Transferability banded per the blueprint (0.65 / 0.75 / 0.85 / 0.95)
- `transferability` moved into `subscores` to match the blueprint item schema
- Section quotas expressed as min/max; the 70/30 split may deviate by at most 2
  slots and only to reach a viable issue length
- Top 3 now reserves a slot for a foreign item
- Alerts restricted to the four hard categories and capped per rolling 30 days
- Newsletter template gained the missing detail block, 2-3 source links, TL;DR,
  reading time, preheader and medico-legal disclaimer
- Timezone-aware datetimes throughout; the DB layer normalises to naive UTC
- Test suite consolidated to the critical paths

### Fixed
- `pyproject.toml` declared `[project.scripts]` before `dependencies`, so TOML
  absorbed the dependency list into the scripts table and the package could not
  be installed at all
- `/api/subscribe` returned the confirmation token in its response, letting
  anyone confirm an address they do not own. The token is now only emailed
- Multi-recipient sends disclosed the whole subscriber list in `To`; they now use
  `Bcc`
- `db/engine.py` declared a second `Base`, so `create_tables()` created nothing
- `migrations/versions/` was empty despite Alembic being wired up
- Dead `/preferences` and `/review/{week}` links in the newsletter footer and logs
- `cross_source_support` was written but never called; it now corroborates
  AIFA <-> EMA and ISS <-> Ministry items
- Deprecated `datetime.utcnow()` and `@app.on_event("startup")`

### Removed
- `delivery/review_api.py`, an unmounted in-memory stub replaced by the real
  review workbench

## [1.0.0] - 2026-04-29

### Added
- Full 7-phase daily pipeline: ingest, classify, score, synthesize, compose, render, send
- 12 RSS source connectors (SIP, SIN, EJP, ADC, Frontiers, Acta Paediatrica, EAP, Lancet Child, Pediatric Research, Bambino Gesu, Gaslini, UPPA)
- Azure OpenAI integration (GPT-5.2) for classification, scoring, and editorial synthesis
- 7-dimension scoring engine (PLS relevance, clinical impact, operational impact, source trust, novelty, actionability, urgency)
- Claim verification pipeline with confidence badges (high/medium/low)
- Newsletter composer with 70/30 IT/foreign ratio enforcement
- Section-based layout: top priority, clinical, regulatory, device, CME
- Professional HTML email template with gradient header, TOC, color-coded section pills, source attribution, and "Leggi tutto" links
- Plain text fallback rendering
- Gmail SMTP_SSL delivery (port 465, app passwords)
- SQLite database with SQLAlchemy 2.0 async ORM
- URL-based deduplication against DB
- `sent_at` tracking - items never repeated across newsletter issues
- Backlog fallback system: pulls from 7-28 day unsent pool when fresh candidates are sparse
- Trigger-based alert system for urgent items (AIFA, FSN, epidemic peaks)
- FastAPI review API for human-in-the-loop approval
- Structured JSON logging and quality metrics
- 127 tests (unit + integration) at the 1.0.0 baseline
- Quality gates script (`vibe-check.ps1`): ruff lint, ruff format, pyright strict, pytest + coverage
- CLI entry point: `python -m oykos` or `oykos` console script
- Comprehensive documentation: PRD, architecture, data model, scoring, source registry
