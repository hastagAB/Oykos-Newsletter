# Source Registry Reference

This document defines the complete source whitelist. Code in `src/oykos/sources.py` must match.

---

## Tier 1 - Italian Institutional (Core Feed)

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `min_salute_pnpv` | Ministry - PNPV/Vaccinations | scrape | https://www.salute.gov.it/new/it/tema/vaccinazioni/piano-nazionale-prevenzione-vaccinale/ | 5 |
| `respivirnet` | RespiVirNet (ISS) | scrape | https://www.salute.gov.it/new/it/tema/influenza/sistema-di-sorveglianza-respivirnet/ | 5 |
| `min_salute_fsn` | Ministry - Device Safety (FSN) | scrape | https://www.salute.gov.it/new/it/avvisi/avvisi-di-sicurezza-sui-dispositivi-medici/ | 5 |
| `min_salute_dm_db` | Ministry - Device Database | scrape | https://www.salute.gov.it/new/it/banche-dati/banca-dati-nazionale-dei-dispositivi-medici/ | 5 |
| `iss_epicentro` | ISS/EpiCentro Influenza | scrape | https://www.epicentro.iss.it/influenza/bollettini | 5 |
| `iss_abr` | ISS - Antibiotic Resistance | scrape | https://www.epicentro.iss.it/antibiotico-resistenza/documentazione-italia | 5 |
| `aifa_safety` | AIFA Safety Communications | scrape | https://www.aifa.gov.it/comunicazioni-di-sicurezza | 5 |
| `sisac_acn` | SISAC - ACN Publications | scrape | https://www.sisac.info/ | 5 |
| `sip` | SIP (Societa Italiana di Pediatria) | rss | https://sip.it/feed/ | 4 |
| `sip_guidelines` | SIP Guidelines | scrape | https://sip.it/sezione/formazione-e-aggiornamento/linee-guida/ | 4 |
| `fimp` | FIMP Nazionale | rss | https://www.fimp.pro/feed/ | 4 |
| `fimp_events` | FIMP Events/Congresses | scrape | https://www.fimp.pro/eventi/eventi-in-presenza/prossimi-eventi | 4 |
| `fimp_calendar` | FIMP Event Calendar | scrape | https://www.fimp.pro/eventi/calendario-eventi | 4 |
| `sicupp` | SICuPP Guidelines Commentate | scrape | https://sicupp.org/category/linee-guida-commentate/ | 4 |
| `sipps` | SIPPS | scrape | https://www.sipps.it/ | 4 |
| `agenas_ecm` | Agenas ECM Events | api | https://ape.agenas.it/Tools/Eventi.aspx | 4 |
| `ecm_portal` | ECM Commission Portal | scrape | https://ecm.agenas.it/ | 4 |
| `garante_privacy` | Garante Privacy | scrape | https://www.garanteprivacy.it/ | 5 |
| `choosing_wisely_it` | Choosing Wisely Italy | scrape | https://choosingwiselyitaly.org/progetto/ | 4 |
| `sin_neonatologia` | SIN (Neonatologia) | rss | https://www.neonatologia.it/feed/ | 4 |

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

## Tier 3 - Global (Conditional Transferability)

| Key | Name | Type | URL | Reliability |
|-----|------|------|-----|-------------|
| `aap_guidelines` | AAP Clinical Practice Guidelines | scrape | https://publications.aap.org/collection/523/Clinical-Practice-Guidelines | 3 |
| `aap_news` | AAP News | rss | https://publications.aap.org/rss/site_154/48.xml | 3 |
| `jama_ped` | JAMA Pediatrics | rss | https://jamanetwork.com/rss/site_16/116.xml | 3 |
| `lancet_child` | Lancet Child & Adolescent Health | rss | https://www.thelancet.com/rssfeed/lanchi_current.xml | 3 |
| `bmc_ped` | BMC Pediatrics | rss | https://bmcpediatr.biomedcentral.com/articles/most-recent/rss.xml | 3 |
| `ped_research` | Pediatric Research | rss | https://www.nature.com/pr.rss | 3 |
| `who` | WHO Publications | scrape | https://www.who.int/ | 5 |

## Radar (Secondary - Triangulation Only)

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

| Source Type | Timeout | Max Items | Rate Limit |
|-------------|---------|-----------|------------|
| RSS/Atom | 30s | 20 per feed | 1 req/source/run |
| Scrape | 45s | 10 per page | 1 req/2s (polite) |
| API | 30s | 50 per query | Per API limits |
| PDF | 60s | 5 per source | 1 req/5s |
