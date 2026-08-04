# Backlog - Italian Pediatrics Newsletter Engine

Phases 1-8 shipped in v1.1.0 (blueprint conformance pass, 2026-07-28). Phase 9
is the scope cut that followed, plus the three additions. See CHANGELOG.md,
`.vibe/decisions/ADR-001-blueprint-conformance.md` and `docs/deviations.md`.

Slices marked **[cut]** shipped in 1.1.0 and were subsequently removed. They are
kept here so the history reads honestly rather than pretending they never
existed.

## Phase 1: Foundation & Data Model
> E2E test: Load config, create a valid `NewsItem` from fixture data, persist to DB, retrieve it, confirm all fields round-trip.

- [x] **S001** - Project skeleton + config + env loading | P0
- [x] **S002** - Source registry (whitelist with tiers + metadata) | P0
- [x] **S003** - Taxonomy enum + validation | P0
- [x] **S004** - NewsItem data model (Pydantic, matches plan schema) | P0
- [x] **S005** - Database schema + repository layer | P0
- [x] **S006** - Phase 1 E2E test | P0

## Phase 2: Ingestion Pipeline
> E2E test: Ingest from real sources, normalize, dedup, persist - verify items in DB with correct metadata.

- [x] **S007** - RSS/Atom connector (feedparser) | P0
- [x] **S007b** - Controlled HTML scraper (unlocks the Tier-1 core feed) | P0
- [x] ~~**S007c** - PDF connector (guidelines, circulars, consensus)~~ **[cut]** | P1
- [x] **S008** - Content normalizer (clean text, language, timestamps, metadata) | P0
- [x] **S009** - Deduplication engine (canonical URL + title similarity 0.85 / 28 days) | P0
- [x] **S010** - Daily ingestion orchestrator | P0
- [x] **S011** - Phase 2 E2E test | P0

## Phase 3: Scoring & Classification
> E2E test: Given candidate items, classify, score, rank - output slots with correct 70/30 ratio and section quotas.

- [x] **S012** - Taxonomy classifier (LLM structured output, triage model) | P0
- [x] **S013** - 7-dimension scoring engine + hard rules | P0
- [x] **S014** - Transferability multiplier for foreign items | P1
- [x] **S014b** - Three selection gates + exclusion criteria | P0
- [x] **S014c** - Noise penalty detection (now in `processing/scoring.py`) | P0
- [x] **S015** - Candidate ranker with constraints (hard 70/30 caps, section quotas) | P0
- [x] **S016** - Phase 3 E2E test | P0

## Phase 4: LLM Synthesis & Verification
> E2E test: Given ranked items, produce editorial pack with structured output - all claims have citations, confidence assigned.

- [x] **S017** - OpenAI client wrapper (Responses API + Structured Outputs) | P0
- [x] **S018** - Evidence snippet extraction with verbatim guard | P0
- [x] **S019** - Editorial synthesis (headline, why-matters, do/avoid, summary) | P0
- [x] **S020** - Claim verification + confidence gating + blocking | P0
- [x] **S020b** - Cross-source corroboration (AIFA <-> EMA, ISS <-> Ministry) | P1
- [x] **S021** - Phase 4 E2E test | P0

## Phase 5: Newsletter Composition
> E2E test: Compose full newsletter HTML + plain text, validate structure, subject line generated.

- [x] **S022** - Weekly composer with slot constraints | P0
- [x] **S023** - Newsletter HTML template (5-block items, TL;DR, reading time) | P0
- [x] **S024** - Subject line generator + preheader (benefit-driven, single variant, triage model) | P1
- [x] **S025** - Plain text fallback | P1
- [x] ~~**S025b** - Device/POCT Decision Cards + "when NOT to test" box~~ **[cut]** | P0
- [x] **S026** - Phase 5 E2E test | P0

## Phase 6: Review & Delivery
> E2E test: Newsletter goes through review interface, gets approved, sends, articles marked sent.

- [x] **S027** - Editorial review workbench (auth, approve/edit/reject, audit trail) | P0
- [x] ~~**S027b** - Risk-based review policy (mandatory + 20% sampling)~~ **[cut]** - every item is reviewed | P0
- [x] **S028** - Email delivery (SMTP, Bcc privacy, per-subscriber messages) | P0
- [x] **S029** - Deliverability headers (List-Unsubscribe RFC 8058) | P0
- [x] **S030** - Feedback collection with structured signals | P1
- [x] **S030b** - Subscriber preferences page (topics, alerts, region) | P1
- [x] **S031** - Phase 6 E2E test | P0

## Phase 7: Trigger Alerts
> E2E test: AIFA safety communication triggers alert pipeline within the monthly cap.

- [x] **S032** - Alert trigger rules (4 hard categories only) | P1
- [x] **S033** - Alert template (urgent format) | P1
- [x] **S034** - Alert delivery pipeline + monthly cap + no repeats | P1
- [x] **S035** - Phase 7 E2E test | P1

## Phase 8: Quality & Observability
> E2E test: Full pipeline run produces structured logs and quality metrics.

- [x] **S036** - Structured logging per pipeline run | P1
- [x] **S037** - Quality metrics (coverage per area, groundedness, ratio) | P2
- [x] ~~**S038** - Offline eval framework (NDCG@k, groundedness, corrections rate)~~ **[cut]** | P2
- [x] **S039** - Phase 8 E2E test | P2

## Phase 9: Scope cut and publishing (unreleased)
> E2E test: A composed issue is held for review, approved, published to WordPress, and delivered with a working "Leggi online" link.

- [x] **S045** - Remove Radar section; exclude preprints and low-trust items at the gates | P0
- [x] **S046** - Remove Decision Cards, A/B subject testing, referrals, archive search | P1
- [x] **S047** - Remove semantic dedup, PDF ingestion, Prefect flows, eval harness | P1
- [x] **S048** - Remove the auto-approval policy; every item requires sign-off | P0
- [x] **S049** - Remove geo-cap relaxation; hard Italy/foreign caps | P1
- [x] **S050** - WordPress publishing before delivery, `Newsletter.public_url` | P0
- [x] **S051** - Closing CTA in HTML and plain text | P1
- [x] **S052** - Nature Medicine, npj Digital Medicine, Lancet Digital Health + 2 taxonomy tags | P1
- [x] **S053** - `oykos check-sources` CLI health check | P1
- [x] **S054** - Rank before synthesis; subject line on the triage model | P0
- [x] **S055** - Documentation reconciliation + `docs/deviations.md` | P1

---

## Next up (not started)

- [x] **S056** - Drop `prefect`, `pgvector`, `sendgrid`, `pypdf` from `pyproject.toml`; drop the stale `flows.py` pyright exclude | P0
- [x] **S057** - Correct `.github/copilot-instructions.md`: no Prefect, no SendGrid | P1
- [ ] **S058** - Alembic migration dropping `embedding`, `subject_variant`, `ab_group` and the referral columns | P1
- [ ] **S059** - Bump the version constant in `__main__.py` and `web/app.py`, tag the release | P1
- [ ] **S060** - Click tracking on the "Leggi online" link, as a usable engagement metric | P2
- [ ] **S044** - Per-source scraper selectors, tuned against live pages | P1
- [ ] **S040** - Per-subscriber issue personalisation using stored topic preferences | P2
- [ ] **S041** - Learning-to-rank re-weighting for user clusters | P2
- [ ] **S043** - Postmaster Tools reporting into the quality dashboard | P2

Anything in `docs/deviations.md` is not on this list on purpose. Each cut feature
has a stated trigger; when the trigger fires, it gets a slice number then.
