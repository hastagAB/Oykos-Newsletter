# PRD: Italian Pediatrics Newsletter Engine (Oykos)

## Product Vision
An "operational intelligence briefing for PLS" (Pediatricians of Free Choice) - not a media product. Every item answers 3 questions in 20-40 seconds: What happened? Why does it matter for a PLS? What changes tomorrow morning in the studio?

## Target User
Italian pediatrician of free choice (PLS) with outpatient clinic. Affiliated professional immersed in obligations and organizational changes (ACN, territorial networks), with a real-time job (triage, visits, certifications, prevention, vaccinations, respiratory infections).

## Jobs to Be Done
1. **Reduce clinical uncertainty** - quickly understand if a novelty impacts diagnosis/therapy/triage
2. **Remain compliant and protected** - privacy/health data, communication rules, obligations, responsibilities
3. **Don't miss hard updates** - drug safety (AIFA), vaccination/ministerial/ISS updates (seasonal)
4. **Better manage the practice** - reduce load/friction (recalls, parent comms, follow-up, digitization)
5. **Evaluate useful tech/tests** - what has evidence, is sustainable, regulated, or recalled

## Guiding Principle
The newsletter saves **time + risk** (clinical/legal/organizational). If it reduces neither, it is noise.

---

## Frequency
- **Weekly Core Digest**: Monday or Friday, 10-12 items, 6-8 min reading time
- **Trigger Alerts**: Max 1-2/month, only for "hard" events (AIFA safety, device FSN, epidemic peaks, ACN changes)

## Newsletter Structure (12 items per issue)
| Section | Items | Description |
|---------|-------|-------------|
| Top Priority | 3 | Must-read: 1-2 Italy + 1 EU/ECDC if relevant |
| Territory Clinical | 2-3 | Respiratory, GI, dermatology, allergology, neuro-dev, triage |
| Regulatory/Compliance | 1-2 | ACN, privacy, telemedicine, prescriptive |
| Device/Test/POCT | 2 | Evidence-based diagnostics + safety alerts |
| CME/Events | 1-2 | Agenas ECM + FIMP/SIP congresses |

## Item Format (5-block template)
1. Operational headline (max 90 characters)
2. Why it counts for PLS (1 sentence)
3. Do/avoid (2-4 bullet micro)
4. Clinical/operational detail (3-6 lines)
5. Sources (2-3 links) + Confidence badge (High/Med/Low)

## Ratio Rule
70% Italy / 30% foreign transferable - enforced on final published slots, not on raw sources.

---

## Selection Gates
An item enters the candidate set only if it passes ALL 3:
- **Gate 1 - PLS Relevance**: impacts territorial clinical decision, studio org, obligation, implementable device, or useful training
- **Gate 2 - Reliability**: institutional/society/journal source; secondary only if it links primary
- **Gate 3 - Actionability**: at least one recommended action or risk-reducing novelty

## Exclusion Criteria
- No generalist medical news without change-in-practice
- No preprints as main item (Radar only, low confidence badge)
- No company marketing as primary source (FSN/corrective actions only)

---

## Scoring (0-100, additive + constraints)
| Dimension | Definition | Scale | Weight |
|-----------|-----------|-------|--------|
| PLS Relevance | Impact on outpatient/triage decision | 0-5 | 22% |
| Clinical/Safety Impact | Reduces risk or changes management | 0-5 | 18% |
| Operational Impact | Changes workflow, timing, communication | 0-5 | 15% |
| Source Reliability | Institutional/primary vs secondary | 0-5 | 15% |
| Novelty | New vs last 4 weeks knowledge base | 0-5 | 10% |
| Actionability | "What to do tomorrow" | 0-5 | 10% |
| Urgency | Seasonal, expires, or immediate impact | 0-5 | 10% |

### Hard Rules
- Source reliability <= 2: cannot be in Top 5, "Radar" only
- Foreign items: apply transferability multiplier (0.6-1.0)
- Noise penalties: duplicates (-10), unverifiable paywall (-10), press release without data (-20)

---

## Content Taxonomy
- **Clinic Territory**: Respiratory/fever, GI/dehydration, dermatology, allergology/asthma, neuro-dev, emergencies/triage
- **Prevention & Public Health**: Vaccinations (PNPV), surveillance (RespiVirNet), antibiotic resistance
- **Medications**: Safety (AIFA/EMA), authorization changes, shortages
- **Studio & Compliance**: ACN/agreements, privacy, telemedicine
- **Diagnostics & POCT**: Rapid tests, POCT lab, functional diagnostics, screening, safety alerts/FSN/recalls
- **Training**: CME (Agenas), congresses (FIMP/SIP/SIPPS/SICuPP)

---

## Source Tiers

### Tier 1 - Italian Institutional (Core Feed)
Ministry of Health (PNPV, RespiVirNet, FSN/device alerts, DM database), ISS/EpiCentro, AIFA, SISAC/ACN, SIP, FIMP, SICuPP, SIPPS, Agenas ECM, Garante Privacy, Choosing Wisely Italy

### Tier 2 - European (High Transferability)
ECDC CDTR (weekly), EMA news/PRAC/paediatric medicines, European Journal of Pediatrics, Archives of Disease in Childhood (BMJ), Frontiers in Pediatrics

### Tier 3 - Global (Conditional Transferability)
AAP, JAMA Pediatrics, Lancet Child, BMC Pediatrics, Pediatric Research, NICE (when not NHS-dependent)

### Radar (Secondary, Triangulation Only)
Pediatric IRCCS (Bambino Gesu), Italian clinical portals (Il Medico Pediatra), Regions/ASLs, health newspapers

---

## Device/POCT Decision Card Fields
Use case, evidence level, performance (sens/spec), workflow, decision impact, costs, regulatory/safety, reimbursement, recommendation (Adopt/Evaluate/Not Priority) + "when NOT to test" appropriateness box.

---

## Deliverability Requirements
- SPF, DKIM, DMARC implemented
- Spam complaint rate < 0.1%
- One-click List-Unsubscribe (RFC 8058)
- Dedicated sending domain with warm-up

## Success KPIs
- Subscription retention (monthly churn)
- Weekly engaged rate (open + action)
- Perceived value micro-survey (1-5)
- Coverage: every core area represented each week
- Corrections rate (must trend down)
- Factuality: % claims with source support
