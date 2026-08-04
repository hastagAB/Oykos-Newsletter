# ADR 001 - Full blueprint conformance

Date: 2026-07-28
Status: Accepted

## Context

The v1.0.0 implementation diverged from the product blueprint in several
load-bearing ways. The divergences were not cosmetic: three of them meant the
product could not do what it claims.

1. **The Tier-1 core feed was unreachable.** Every Italian institutional source
   (Ministry, AIFA, ISS/EpiCentro, SISAC, Garante Privacy, Agenas) and both EU
   regulators (ECDC, EMA) are declared `SourceType.SCRAPE` or `API`, and only the
   RSS connector existed. The ingestion orchestrator logged "skipping non-RSS
   source" and returned nothing for all of them.
2. **No grounding.** `key_passages` was declared in the data model but never
   populated. Editorial synthesis ran directly on `raw_text`, verification could
   only nudge a confidence value, and nothing could ever be blocked. The
   blueprint's first non-negotiable principle is source -> claim traceability.
3. **Structured Outputs were simulated.** The LLM client injected a JSON schema
   into the system prompt and stripped markdown fences from the reply. The
   blueprint and `.github/copilot-instructions.md` both require real Structured
   Outputs.

Alongside these, the three selection gates, the noise penalties, the Decision
Card, the risk-based review policy, the Radar section and the alert cap were
specified but absent.

## Decision

Bring the implementation to the blueprint, accepting changes to the three
documents marked "do not touch without ADR".

### Data model (`docs/data-model.md`)

* `transferability` moves from `ScoringBlock` into `Subscores`, matching the
  blueprint item schema literally. `ScoringBlock.transferability` remains as a
  read-only property so there is exactly one writer.
* New `Gating` block records the outcome of the three selection gates.
* New `DecisionCard` model for the device/POCT section.
* `EditorialBlock` gains `unsupported_claims` and `blocked`.
* `ReviewStatus` gains `review_reason`.
* `Newsletter` gains `preheader`, `tldr` and `reading_time_minutes`.
* `NewsletterSlot` gains `source_links` and `decision_card`.
* All datetimes are timezone-aware in the domain model; the database layer
  normalises to naive UTC at the boundary so SQLite and PostgreSQL agree.

### Scoring (`docs/scoring.md`)

* Transferability is banded per the blueprint rather than a flat 0.7 for
  everything non-EU: EU regulatory 0.95, EU guideline 0.85, portable evidence
  0.75, US/UK system-dependent 0.65.
* Section quotas become minimum/maximum pairs and gain a `RADAR` section that
  borrows unused capacity inside the same 12-slot budget.
* The 70/30 split may deviate by at most `MAX_GEO_DEVIATION` (2) and only to
  reach `MIN_VIABLE_TOTAL` (10). Shipping a shorter issue beats shipping a
  lopsided one.
* The duplicate penalty threshold (0.75) sits deliberately *below* the dedup
  threshold (0.85). Above 0.85 an item is dropped; the band between the two is
  "same news rewritten" and only earns a penalty.

### Sources (`docs/sources.md`)

* Added the controlled scraper, which activates every Tier-1 and Tier-2 source
  already on the whitelist.
* Added the regional sources the blueprint calls out (Lombardia, Veneto,
  Umbria), NICE, the Ministry device-incident reporting system, the IVDR
  performance-studies page and Agenas HTA.
* `agenas_ecm` changes from `API` to `SCRAPE`. The blueprint suggests an API,
  but the Agenas ECM contract is not documented publicly and inventing a client
  for it would violate the stop directive in the project instructions.

## Consequences

* Alert volume drops sharply. Guidelines, drug shortages, generic legal updates
  and vaccination news no longer trigger alerts; they are digest material. Only
  four hard categories remain, capped at 2 per rolling 30 days.
* Items can now be refused. Verification blocks an item with no evidence at all,
  or with two or more unsupported claims. `get_unsent_candidates` and
  `get_backlog` filter blocked items out.
* Most issues will be held for review, because the Top 3 always require
  sign-off. This is the intended behaviour, not a regression.
* Scraping introduces a politeness obligation: a declared user agent, bounded
  concurrency and a per-source page cap. Sources are an explicit allow-list.
* `oykos` now has `ingest` (daily) and `compose` (weekly) subcommands. The bare
  `oykos` command runs both, which is what the Docker `pipeline` service uses.

## Alternatives considered

* **Keep the prompt-injected JSON schema.** Rejected: it fails silently and
  unrecoverably when a model wraps output differently, and it is explicitly
  forbidden by the project instructions.
* **Drop the scrape-only sources from the registry.** Rejected: that would mean
  abandoning the entire Italian institutional core feed, which is the product.
* **Let the geo split skew freely to always fill 12 slots.** Rejected: the
  blueprint permits the deviation only for exceptional weeks, and an unbounded
  relaxation produced an 11/1 split in testing.
