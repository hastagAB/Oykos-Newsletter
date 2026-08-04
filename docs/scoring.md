# Scoring Engine Reference

## Weighted Dimensions (0-100 scale)

Each dimension scored 0-5, then weighted and summed to produce a raw score.

| # | Dimension | Weight | Operational Definition |
|---|-----------|--------|----------------------|
| 1 | PLS Relevance | 22% | Impact on typical outpatient/triage decision |
| 2 | Clinical/Safety Impact | 18% | Reduces clinical risk or changes management |
| 3 | Operational Impact | 15% | Changes workflow, timing, communication, fulfillment |
| 4 | Source Reliability | 15% | Institutional/society/primary vs secondary |
| 5 | Novelty | 10% | New compared to knowledge base + last 4 weeks |
| 6 | Actionability | 10% | "What to do tomorrow": check, avoid, adopt, explain |
| 7 | Urgency | 10% | Expires, is seasonal, or impacts immediately |

### Score calculation
```
raw_score = sum(subscore_i * weight_i) * (100 / 5)
# e.g. all 5s = (5*0.22 + 5*0.18 + 5*0.15 + 5*0.15 + 5*0.10 + 5*0.10 + 5*0.10) * 20 = 100
```

### Transferability multiplier (foreign items only)
```
final_score = penalized_score * transferability
```

Implemented in `oykos.processing.scoring.compute_transferability`:

| Band | Value | Applies to |
|------|-------|-----------|
| EU regulatory | 0.95 | Source key contains `ema`, `ecdc`, `who`, `eu_` |
| EU guideline | 0.85 | `Geo.EU` with a guideline/consensus/safety/surveillance document type |
| Portable evidence | 0.75 | `Geo.EU` otherwise, or a US/UK guideline from a trusted source |
| System dependent | 0.65 | US/UK material tied to their own reimbursement pathway |

Italian items are always 1.0. The value is stored in `Subscores.transferability`.

---

## Selection gates

An item enters the candidate set only if it clears all three gates
(`oykos.processing.gates`):

1. **PLS relevance** - at least one taxonomy tag and `pls_relevance >= 2`.
2. **Reliability** - `reliability_tier >= 2`, or a secondary source that links or
   cites one of the institutional primary domains.
3. **Actionability** - explicit `what_to_do` actions, or an inherently actionable
   document type, or `actionability >= 2`.

### Exclusion criteria

An item matching any of these is dropped, whatever it scored.

| Reason | Trigger |
|--------|---------|
| `no_pls_relevance` | No taxonomy tag, or `pls_relevance < 2` |
| `unreliable_source` | `source_trust <= 2`, or `reliability_tier < 2` without a primary-source citation |
| `not_actionable` | No actions, not an actionable document type, `actionability < 2` |
| `generalist_news` | `DocumentType.NEWS` with clinical, operational and actionability subscores all below 2 |
| `vendor_marketing` | Marketing copy from a tier 0-1 source |
| `preprint` | Preprint, medRxiv/bioRxiv, or explicitly not peer reviewed |

Preprints and low-trust items are **excluded, not demoted**. There is no Radar
section to route them into - see [deviations.md](deviations.md).

---

## Hard Rules

### Gate rules
- `source_trust <= 2` vetoes the reliability gate outright. The registry tier
  says what a source usually is, the subscore says what this particular item
  actually is, and the harsher of the two wins.
- An item blocked by verification (no evidence, or two or more unsupported
  claims) is excluded from candidate queries entirely.

### Noise penalties (applied to raw_score)
| Penalty | Points | Trigger |
|---------|--------|---------|
| Duplicate | -10 | Title similarity >= 0.75 against recent titles |
| Paywall | -10 | Content unverifiable behind a paywall |
| Press release | -20 | PR copy with no figures to check |
| Single source | -5 | Reliability tier < 3 with at most one citation |

Detected by `oykos.processing.scoring.detect_penalties`, called from the daily
ingestion orchestrator. (It used to live in `processing/penalties.py`; that
module is gone.)

### The two title-similarity thresholds

Two different thresholds compare titles, and the difference is deliberate.

| Constant | Value | Location | Effect |
|----------|-------|----------|--------|
| `TITLE_SIMILARITY_THRESHOLD` | **0.85** | `oykos.ingestion.dedup` | Item is dropped at ingestion, never enters the pool |
| `DUPLICATE_TITLE_THRESHOLD` | **0.75** | `oykos.processing.scoring` | Item survives but takes the -10 duplicate penalty |

Both compare against titles from the last 28 days
(`dedup.RECENT_WINDOW_DAYS`), using `difflib.SequenceMatcher` on lowercased,
stripped titles.

The penalty threshold is the **looser** of the two on purpose. Dropping an item
is irreversible: a false positive means real news is silently lost, so the drop
threshold is set high enough that only near-identical titles trigger it. The
0.75-0.85 band is where "the same news, rewritten" lives - a republication, a
secondary outlet's version of a Ministry notice. Those are usually genuine but
rarely the best version, so they stay in the pool and simply rank lower. A
penalty is recoverable; a drop is not.

### Composition constraints (applied during ranking)

12 slots, filled in two passes: every section to its minimum first, then the
remaining budget by score up to each maximum.

| Section | Min | Max |
|---------|-----|-----|
| Top Priority | 3 | 3 |
| Clinical | 2 | 3 |
| Regulatory | 1 | 2 |
| Device / Test | 1 | 2 |
| CME / Events | 1 | 2 |

- **Italy/abroad ratio**: 8 Italian slots / 4 foreign slots. These are hard
  caps. There is no relaxation pass: a thin week produces a shorter issue rather
  than a lopsided or padded one.
- **Top 3**: at most 2 Italian items (`MAX_ITALY_IN_TOP_PRIORITY`), so the
  section is never all-domestic.
- **Editorial headroom**: the weekly pipeline shortlists 3 items beyond the
  final budget, so an item blocked by verification does not shorten the issue.
- **Minimum coverage**: the quality report flags any core area (clinical,
  prevention, medication, compliance, device, training) that had material
  available but did not make the issue.

---

## Source Reliability Mapping

| Level | Score | Examples |
|-------|-------|---------|
| 5 | Institutional regulator | Ministry of Health, AIFA, ISS, EMA, ECDC |
| 4 | National scientific society | SIP, FIMP, SICuPP, SIPPS |
| 3 | Peer-reviewed journal | JAMA Pediatrics, Lancet Child, EJP, Nature Medicine |
| 2 | Institutional hospital/IRCCS | Bambino Gesu, Meyer, Gaslini |
| 1 | Secondary press/portal | Health newspapers, blogs |
| 0 | Unverified/marketing | Company press releases |

This is `Source.reliability` in the registry - the tier's prior. The
`source_trust` subscore is the model's judgement about the specific item, and
the reliability gate applies whichever of the two is harsher.
