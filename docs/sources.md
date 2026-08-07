# Source Registry Reference

This document defines the complete source whitelist. Code in
`src/oykos/models/source.py` must match - 50 sources across 4 tiers.

Run `oykos check-sources` to fetch every enabled source concurrently and see
which ones are still returning items. Feed URLs rot and scraper selectors drift;
that command is how you find out before an issue comes up short.

---

## Tier 1 - Italian Institutional (Core Feed)

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `min_salute_pnpv` | Ministry - PNPV/Vaccinations | scrape | https://www.salute.gov.it/new/it/tema/vaccinazioni/piano-nazionale-prevenzione-vaccinale/ | 5 |
| `respivirnet` | RespiVirNet (ISS) | scrape | https://www.salute.gov.it/new/it/tema/influenza/sistema-di-sorveglianza-respivirnet/ | 5 |
| `min_salute_fsn` | Ministry - Device Safety (FSN) | scrape | https://www.salute.gov.it/new/it/avvisi/avvisi-di-sicurezza-sui-dispositivi-medici/ | 5 |
| `min_salute_dm_db` | Ministry - Device Database | scrape | https://www.salute.gov.it/new/it/banche-dati/banca-dati-nazionale-dei-dispositivi-medici/ | 5 |
| `min_salute_segnalazioni` | Ministry - Device Incident Reporting | scrape | https://www.salute.gov.it/new/it/tema/dispositivi-medici/sistema-di-segnalazione-i-dispositivi-medici/ | 5 |
| `min_salute_ivdr` | Ministry - IVD Performance Studies (IVDR) | scrape | https://www.salute.gov.it/new/it/tema/dispositivi-medici/studi-delle-prestazioni-dei-dispositivi-medico-diagnostici-vitro/ | 5 |
| `iss_epicentro` | ISS/EpiCentro Influenza | scrape | https://www.epicentro.iss.it/influenza/bollettini | 5 |
| `iss_abr` | ISS - Antibiotic Resistance | scrape | https://www.epicentro.iss.it/antibiotico-resistenza/documentazione-italia | 5 |
| `aifa_safety` | AIFA Safety Communications | scrape | https://www.aifa.gov.it/comunicazioni-di-sicurezza | 5 |
| `sisac_acn` | SISAC - ACN Publications | scrape | https://www.sisac.info/ | 5 |
| `garante_privacy` | Garante Privacy | scrape | https://www.garanteprivacy.it/ | 5 |
| `sip` | SIP (Societa Italiana di Pediatria) | rss | https://sip.it/feed/ | 4 |
| `sip_guidelines` | SIP Guidelines | scrape | https://sip.it/sezione/formazione-e-aggiornamento/linee-guida/ | 4 |
| `fimp` | FIMP Nazionale | rss | https://www.fimp.pro/feed/ | 4 |
| `fimp_events` | FIMP Events/Congresses | scrape | https://www.fimp.pro/eventi/eventi-in-presenza/prossimi-eventi | 4 |
| `fimp_calendar` | FIMP Event Calendar | scrape | https://www.fimp.pro/eventi/calendario-eventi | 4 |
| `sicupp` | SICuPP Guidelines Commentate | scrape | https://sicupp.org/category/linee-guida-commentate/ | 4 |
| `sipps` | SIPPS | scrape | https://www.sipps.it/ | 4 |
| `sin_neonatologia` | SIN (Neonatologia) | rss | https://www.neonatologia.it/feed/ | 4 |
| `agenas_ecm` | Agenas ECM Events | scrape | https://ape.agenas.it/Tools/Eventi.aspx | 4 |
| `ecm_portal` | ECM Commission Portal | scrape | https://ecm.agenas.it/ | 4 |
| `agenas_hta` | Agenas - HTA Medical Devices | scrape | https://www.agenas.gov.it/ | 4 |
| `choosing_wisely_it` | Choosing Wisely Italy | scrape | https://choosingwiselyitaly.org/progetto/ | 4 |

### Tier 1 - Italian regional

Operational changes that affect affiliated PLS in those regions.

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `regione_lombardia` | Regione Lombardia - Sanita | scrape | https://www.regione.lombardia.it/wps/portal/istituzionale/HP/servizi-e-informazioni/cittadini/salute-e-prevenzione | 4 |
| `regione_veneto` | Regione Veneto - Sanita | scrape | https://www.regione.veneto.it/web/sanita | 4 |
| `regione_umbria` | Regione Umbria - Salute | scrape | https://www.regione.umbria.it/salute | 4 |

## Tier 2 - European (High Transferability)

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `ecdc_cdtr` | ECDC Weekly Threats Report | scrape | https://www.ecdc.europa.eu/en/publications-and-data/monitoring/weekly-threats-reports | 5 |
| `ema_news` | EMA News | scrape | https://www.ema.europa.eu/en/news | 5 |
| `ejped` | European Journal of Pediatrics | rss | https://link.springer.com/search.rss?facet-journal-id=431&facet-content-type=Article | 3 |
| `adc_bmj` | Archives of Disease in Childhood | rss | https://adc.bmj.com/rss/current.xml | 3 |
| `frontiers_ped` | Frontiers in Pediatrics | rss | https://www.frontiersin.org/journals/pediatrics/rss | 3 |
| `acta_paed` | Acta Paediatrica | rss | https://rss.onlinelibrary.wiley.com/feed/16512227/most-recent | 3 |
| `eap` | European Academy of Paediatrics | rss | https://www.eapaediatrics.eu/feed/ | 4 |

## Tier 3 - Global

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `aap_guidelines` | AAP Clinical Practice Guidelines | scrape | https://publications.aap.org/collection/523/Clinical-Practice-Guidelines | 4 |
| `europe_pmc` | Europe PMC - Pediatric Evidence | api | https://www.ebi.ac.uk/europepmc/webservices/rest/search | 4 |
| `lancet_child` | Lancet Child & Adolescent Health | rss | https://www.thelancet.com/rssfeed/lanchi_current.xml | 4 |
| `bmc_ped` | BMC Pediatrics | rss | https://bmcpediatr.biomedcentral.com/articles/most-recent/rss.xml | 3 |
| `ped_research` | Pediatric Research | rss | https://www.nature.com/pr.rss | 3 |
| `who_news` | WHO News | rss | https://www.who.int/rss-feeds/news-english.xml | 5 |
| `nice_guidance` | NICE Guidance | scrape | https://www.nice.org.uk/guidance/published?ndt=Guidance | 3 |

### Why Pediatrics and JAMA Pediatrics arrive through Europe PMC

Verified 2026-08-07: `publications.aap.org` returns 403 to automated clients
and the AAP News and JAMA Pediatrics feeds return 404. Rather than keep dead
URLs in the registry, the peer-reviewed literature the editorial feedback asks
for comes through Europe PMC, which indexes the same journals and serves a
documented REST API.

`oykos.ingestion.evidence` queries a named journal list restricted to the last
21 days and drops records without an abstract: a headline alone cannot be
judged. Results are classified and scored like any other candidate.

### Tier 3 - High-impact research and AI in clinical practice

Added to cover the evidence and digital-health material a PLS otherwise only
meets second-hand. All three are RSS and were verified returning entries.

| Key | Name | Type | URL | Reliability | Category hint |
|-----|------|------|-----|-------------|---------------|
| `nature_medicine` | Nature Medicine | rss | https://www.nature.com/nm.rss | 3 | `research_evidence` |
| `npj_digital_medicine` | npj Digital Medicine | rss | https://www.nature.com/npjdigitalmed.rss | 3 | `ai_digital_health` |
| `lancet_digital_health` | Lancet Digital Health | rss | https://www.thelancet.com/rssfeed/landig_current.xml | 3 | `ai_digital_health` |

These are backed by two taxonomy tags added at the same time:
`TaxonomyTag.RESEARCH_EVIDENCE` and `TaxonomyTag.AI_DIGITAL_HEALTH`. Items
tagged `ai_digital_health` route to the Device/Test section.

Being Tier 3, they still have to clear all three selection gates and compete on
relevance to PLS practice. There is no foreign discount and no foreign slot
quota: an international item wins a slot when it is more useful to a PLS than
the domestic alternatives.

## Event sources (separate registry)

The "Prossimi appuntamenti per il PLS" section does not use this registry. It
is driven by `src/oykos/events/data/pls_event_sources.xlsx`, 81 monitored
sources maintained by the editorial team. See `docs/events.md`.

## Radar tier (Secondary - Triangulation Only)

A **source tier**, not a newsletter section. Low reliability means these items
usually fail the reliability gate; they are useful for corroborating a story
that a stronger source also carries.

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `bambino_gesu` | Ospedale Bambino Gesu | rss | https://www.ospedalebambinogesu.it/rss | 2 |
| `meyer` | Ospedale Meyer | rss | https://www.meyer.it/index.php?format=feed&type=rss | 2 |
| `gaslini` | Ospedale Gaslini | rss | https://www.gaslini.org/feed/ | 2 |
| `medico_pediatra` | Il Medico Pediatra | scrape | https://www.ilmedicopediatra-rivistafimp.it/enewsletter/ | 1 |
| `uppa` | UPPA | rss | https://www.uppa.it/feed/ | 1 |
| `medico_bambino` | Medico e Bambino | rss | https://www.medicoebambino.com/rss.php | 2 |

---

## Fetch Config Defaults

| Source Type | Timeout | Max Items |
|-------------|---------|-----------|
| RSS/Atom | 30s | 20 per feed |
| Scrape | 45s | 10 per page |
| ECM listings | 45s | 15 per page |

Set per source via `FetchConfig` in `src/oykos/models/source.py`, which also
carries the optional scraper hints (`link_selector`, `content_selector`,
`url_must_contain`).

`SourceType.PDF` exists in the enum but no source uses it: there is no PDF
connector. See [deviations.md](deviations.md).

## Health checks

```bash
oykos check-sources
```

Fetches every **enabled** source, 5 at a time, with a 45s timeout each, and
prints one line per source:

```
OK   aifa_safety              scrape  8 items
DEAD frontiers_ped            rss     0 items

48/50 sources returned items.
```

Exits non-zero only when nothing at all came back. Sources are sorted with the
failures first.
