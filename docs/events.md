# Upcoming events for PLS

Section 6 of the editorial feedback of 2026-08-07. A separate pipeline from the
news, because events answer a different question.

> Do not ask "Was this event published this week?" Ask "Is this a high relevance
> PLS event happening soon enough that the reader should put it on the calendar
> now?"

## The registry is the map, not the content

`src/oykos/events/data/pls_event_sources.xlsx` holds 81 monitored sources:
scientific societies, PLS organisations, pediatric portals, PCO agencies and ECM
providers. It says *where* to look and *what relevant looks like there*. Event
details always come from the live page.

Fields used: `ID_fonte`, `Nome_fonte`, `Acronimo`, `URL_da_monitorare`,
`URL_secondario`, `Tipo_pagina`, `Dominio`, `Rilevanza_PLS`, `Priorita_bot`,
`Frequenza_check`, `Keyword_filtro`, `Metodo_estrazione_consigliato`,
`Note_operative`.

Priority 1 sources (17 of 81) run every week. The rest rotate, capped by
`MAX_EVENT_SOURCES_PER_RUN`, so a weekly run does not hit all 81.

## Discovery

69 of the 81 rows point at a homepage rather than an event listing, so there is
a discovery stage before extraction: internal links and `sitemap.xml` are
inspected for `eventi`, `congressi`, `corsi`, `formazione`, `ecm`,
`appuntamenti`, `agenda`. A candidate wins by containing several dates, which is
what separates a calendar from an article that mentions one event.

Resolved URLs are cached in `event_sources_resolved` with the verification date.
After `MAX_DISCOVERY_FAILURES` the source is flagged for manual review.

**Archive pages are refused outright.** A list of past editions has more dates
than the upcoming calendar and therefore wins a naive date count: observed on
`fimp.pro`, which resolved to `/eventi/eventi-passati` before the guard existed.

## Extraction

Model-driven with a strict schema (`oykos.events.extractor`). 81 sites do not
share a layout, and per-site parsers fail silently.

The hard data quality rule:

- No start date, or no official URL, means the event is dropped.
- ECM credits, accreditation, fees, deadlines and accredited professions are
  copied from the page or left empty. Never inferred.
- `stated_audience` is copied verbatim, so an editor can check the filter.
- Programme PDFs are followed, because target professions and ECM credits are
  usually stated there rather than on the listing page.

## The audience filter

`pls_fit` records **how** the audience was established, not how relevant it
feels:

| Value | Meaning |
|-------|---------|
| `explicit` | The page names PLS, pediatri di famiglia, cure primarie pediatriche |
| `programme` | Audience not named, but programme topics are clearly outpatient primary care |
| `unsupported` | Neither. Rejected. |

Generic pediatric relevance is not enough.

### The federation exception

The feedback pulls two ways: 6.3 forbids inferring relevance from the promoting
society's name, while the worked example in 6.4 expects Children 2026, a
national FIMP event, to appear.

FIMP, SIMPeF, ACP and SIMPE are the federations **of family pediatricians**, so
their own events have a PLS audience by constitution rather than by inference.
The list is named and narrow, and the upgrade is written into
`programme_evidence` so an editor can see why the audience was accepted. Other
societies (SIP, SIGENP, SIMRI, SINPIA) still need real evidence.

Worth resolving explicitly in the next revision of the guidelines.

## Selection

| Rule | Implementation |
|------|----------------|
| Window | Start date between today and +30 days |
| Congress exception | +90 days for a national PLS congress, for travel and registration planning |
| Cap | Maximum 4. No section at all rather than a padded one |
| Ordering | PLS relevance first, then timing, organiser authority, practical value |
| Deduplication | Normalised title, start date and city. The richest record survives and keeps every source URL |
| Repeat editions | An event may appear in several issues while it is still upcoming |

`first_seen_at`, `last_seen_at` and extraction hashes are crawler metadata.
**They never decide what a reader sees.**

## Operating it

```
oykos events            # crawl, then print what the section would contain
oykos events --offset N # rotate which non-priority sources are crawled
```

The crawl logs scheduled sources, fetches, failures, newly discovered listing
URLs and events extracted, so an empty section can be explained rather than
guessed at.
