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
final_score = raw_score * transferability_factor
```
- EU regulatory (ECDC/EMA): 0.9-1.0
- EU guideline (generalizable): 0.8-0.9
- Solid evidence, not system-dependent: 0.7-0.8
- US/UK system-dependent: 0.6-0.7

---

## Hard Rules

### Gate rules
- `source_trust <= 2`: Item **cannot** appear in Top 5. Eligible only for "Radar" section with low confidence badge.
- Item must pass all 3 selection gates (relevance, reliability, actionability) to enter candidate set.

### Noise penalties (applied to raw_score)
| Penalty | Points | Trigger |
|---------|--------|---------|
| Duplicate | -10 | Near-duplicate of item in last 4 weeks |
| Paywall | -10 | Content unverifiable behind paywall |
| Press release | -20 | Marketing/PR without data or primary source |
| Single source | -5 | Only one secondary source, no primary confirmation |

### Composition constraints (applied during ranking)
- **Italy/abroad ratio**: 8 Italian slots / 4 foreign slots (out of 12)
- **Section caps**: Top Priority 3, Clinical 2-3, Regulatory 1-2, Device 2, CME 1-2
- **Minimum coverage**: At least 1 item from Prevention, 1 from Medication, 1 from Compliance per issue (when available)

---

## Source Reliability Mapping

| Level | Score | Examples |
|-------|-------|---------|
| 5 | Institutional regulator | Ministry of Health, AIFA, ISS, EMA, ECDC |
| 4 | National scientific society | SIP, FIMP, SICuPP, SIPPS |
| 3 | Peer-reviewed journal | JAMA Pediatrics, Lancet Child, EJP |
| 2 | Institutional hospital/IRCCS | Bambino Gesu, Meyer, Gaslini |
| 1 | Secondary press/portal | Health newspapers, blogs |
| 0 | Unverified/marketing | Company press releases |
