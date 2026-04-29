# Backlog - Italian Pediatrics Newsletter Engine

## Phase 1: Foundation & Data Model (~1 week)
> E2E test: Load config, create a valid `NewsItem` from fixture data, persist to DB, retrieve it, confirm all fields round-trip.

- [ ] **S001** - Project skeleton + config + env loading | P0
- [ ] **S002** - Source registry (whitelist with tiers + metadata) | P0 | needs: S001
- [ ] **S003** - Taxonomy enum + validation | P0 | needs: S001
- [ ] **S004** - NewsItem data model (Pydantic, matches plan schema) | P0 | needs: S003
- [ ] **S005** - Database schema + repository layer | P0 | needs: S004
- [ ] **S006** - Phase 1 E2E test | P0 | needs: S005

## Phase 2: Ingestion Pipeline (~1 week)
> E2E test: Ingest from 3 real RSS sources, normalize, dedup, persist - verify items in DB with correct metadata.

- [ ] **S007** - RSS/Atom connector (feedparser) | P0 | needs: S005
- [ ] **S008** - Content normalizer (clean text, language, timestamps, metadata) | P0 | needs: S004
- [ ] **S009** - Deduplication engine (URL hash + title similarity) | P0 | needs: S005
- [ ] **S010** - Daily ingestion orchestrator | P0 | needs: S007, S008, S009
- [ ] **S011** - Phase 2 E2E test | P0 | needs: S010

## Phase 3: Scoring & Classification (~1 week)
> E2E test: Given 30 candidate items (fixture), classify, score, rank - output top 12 with correct 70/30 ratio and section quotas.

- [ ] **S012** - Taxonomy classifier (LLM structured output) | P0 | needs: S010
- [ ] **S013** - 7-dimension scoring engine + hard rules | P0 | needs: S004
- [ ] **S014** - Transferability multiplier for foreign items | P1 | needs: S013
- [ ] **S015** - Candidate ranker with constraints (70/30, section caps) | P0 | needs: S013, S014
- [ ] **S016** - Phase 3 E2E test | P0 | needs: S015

## Phase 4: LLM Synthesis & Verification (~1 week)
> E2E test: Given top 12 ranked items, produce editorial pack with structured output - all claims have citations, confidence assigned.

- [ ] **S017** - OpenAI client wrapper (Responses API + Structured Outputs) | P0 | needs: S001
- [ ] **S018** - Evidence snippet extraction from source content | P0 | needs: S017
- [ ] **S019** - Editorial synthesis (headline, why-matters, do/avoid, summary) | P0 | needs: S017, S018
- [ ] **S020** - Claim verification + confidence gating | P0 | needs: S019
- [ ] **S021** - Phase 4 E2E test | P0 | needs: S020

## Phase 5: Newsletter Composition (~1 week)
> E2E test: Given 12 editorial packs, compose full newsletter HTML + plain text, validate structure (Top 3 + sections), subject line generated.

- [ ] **S022** - Weekly composer with slot constraints | P0 | needs: S015, S020
- [ ] **S023** - Newsletter HTML template (premium, responsive) | P0 | needs: S022
- [ ] **S024** - Subject line generator (benefit-driven) | P1 | needs: S017
- [ ] **S025** - Plain text fallback | P1 | needs: S023
- [ ] **S026** - Phase 5 E2E test | P0 | needs: S023

## Phase 6: Review & Delivery (~1 week)
> E2E test: Newsletter goes through review interface, gets approved, sends via ESP, delivery confirmed, articles marked sent.

- [ ] **S027** - Human review interface (minimal FastAPI app) | P0 | needs: S023
- [ ] **S028** - Email delivery via ESP (SendGrid/Postmark) | P0 | needs: S023
- [ ] **S029** - Deliverability headers (List-Unsubscribe RFC 8058) | P0 | needs: S028
- [ ] **S030** - Feedback collection endpoint | P1 | needs: S028
- [ ] **S031** - Phase 6 E2E test | P0 | needs: S028, S027

## Phase 7: Trigger Alerts (~1 week)
> E2E test: AIFA safety communication detected in ingestion, triggers alert pipeline, sends urgent email within threshold.

- [ ] **S032** - Alert trigger rules (AIFA safety, device FSN, epidemic) | P1 | needs: S010
- [ ] **S033** - Alert template (urgent format) | P1 | needs: S023
- [ ] **S034** - Alert delivery pipeline | P1 | needs: S032, S033, S028
- [ ] **S035** - Phase 7 E2E test | P1 | needs: S034

## Phase 8: Quality & Observability (~1 week)
> E2E test: Full pipeline run produces structured logs, quality metrics computed, coverage report generated.

- [ ] **S036** - Structured logging per pipeline run | P1 | needs: S010
- [ ] **S037** - Quality metrics (coverage per section, corrections rate) | P2 | needs: S036
- [ ] **S038** - Offline eval framework (NDCG@k, groundedness) | P2 | needs: S020
- [ ] **S039** - Phase 8 E2E test | P2 | needs: S037
