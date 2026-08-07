# Scoring Engine Reference

Audience fit is evaluated before source geography. The reader is a Pediatra di
Libera Scelta running an outpatient practice in the territory, not a hospital
pediatrician. A clinically sound story aimed at a hospital team is the wrong
story, however authoritative the source.

## Weighted criteria (0-100 scale)

The five criteria from the editorial feedback of 2026-08-07.

| # | Criterion | Weight | Operational Definition |
|---|-----------|--------|----------------------|
| 1 | PLS practice relevance | 35% | Affects patients, decisions, counselling, follow up or workflow in primary care |
| 2 | Actionability | 25% | The reader can tell what to consider or do differently |
| 3 | Source authority | 15% | Scientifically or institutionally strong, judged on authority alone |
| 4 | Freshness | 15% | Genuinely new for a weekly newsletter |
| 5 | Italian applicability | 10% | The evidence transfers to Italian PLS practice |

Criterion 1 is measured by three subscores blended 60/20/20 across
`pls_relevance`, `operational_impact` and `clinical_impact`, because "affects
decisions, counselling or workflow" is what those three measure together.

### Score calculation
```
raw_score = sum(criterion_i * weight_i) * (100 / 5)
```

Italian applicability is a weighted criterion and **nothing else**. It used to be
applied twice, once here and again as a multiplier on the total, which
double-discounted every foreign item and is what let source geography outrank
audience fit.

The value is judged by the classifier and stored in `Subscores.transferability`.
`oykos.processing.scoring.default_applicability` is a deterministic fallback for
items scored before the criterion existed.

### No geography quota

There is no Italy/foreign split. `rank_and_select` caps only how many items may
come from a single source (2), so no society can dominate an issue. An
international item can fill every slot if it earns them.

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
| Penalty | Points | Trigger | Stage |
|---------|--------|---------|-------|
| Duplicate | -10 | Title similarity >= 0.75 against recent titles | ingest |
| Paywall | -10 | Content unverifiable behind a paywall | ingest |
| Press release | -20 | PR copy with no figures to check | ingest |
| Single source | -5 | Reliability tier < 3 with at most one citation | ingest |
| Hospital only | -25 | `setting=hospital` with no realistic PLS use case | after classification |
| Case report | -15 | A single case with no practice implication | after classification |
| Generic reminder | -12 | Educational recap of settled practice | after classification |

Two stages, and the distinction matters. `detect_penalties` runs during
ingestion and can only read the raw item. `detect_editorial_penalties` runs in
`classify_and_score` because the audience penalties need a judged `setting` and
real subscores; evaluated at ingestion they would always see zeros and could
never fire.

Changing any of this only affects items ingested afterwards. Ingestion
deduplicates, so stored items keep the scores the model of the day gave them.
Run `oykos rescore --days N` to re-judge the backlog.

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

- **No Italy/abroad ratio.** Geography does not decide selection. Italian
  applicability is one weighted criterion inside the score.
- **At most 2 items per source** (`MAX_PER_SOURCE`), so one society cannot
  dominate an issue.
- **No section minimums.** Two strong stories beat three average ones, and the
  system must be willing to discard weak content for "what really changes this
  week" to stay credible.
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
