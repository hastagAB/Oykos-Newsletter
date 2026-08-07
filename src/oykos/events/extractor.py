"""LLM extraction and PLS relevance judgement for events.

Extraction is deliberately model-driven: 81 sites do not share a layout, and a
per-site parser would be brittle in a way that quietly drops events. The model
reads the page and fills a strict schema.

What the model may NOT do is invent. ECM credits, deadlines, accredited
professions and the stated audience are copied from the page or left empty, and
an event whose PLS audience cannot be supported is rejected rather than guessed
at. That is the hard data quality rule from the editorial feedback.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

from oykos.events.models import Event, EventFormat, PLSFit
from oykos.llm.client import LLMClient

logger = logging.getLogger(__name__)

MAX_PAGE_CHARS = 14000
MAX_EVENTS_PER_PAGE = 12

# The Italian federations OF family pediatricians. Their own congresses and
# courses are for PLS by constitution, so the audience is established rather
# than inferred. This is deliberately narrow: it is a named list of PLS
# organisations, NOT a rule that any pediatric society implies relevance.
PLS_ORGANISATIONS = frozenset({"fimp", "simpef", "acp", "simpe"})

CONSTITUTIONAL_EVIDENCE = (
    "Evento della federazione dei pediatri di famiglia: pubblico PLS per statuto."
)
# Stated only as fact. The model leaves why_relevant empty when it judges the
# audience unsupported, and a blank line in the section helps nobody.
CONSTITUTIONAL_WHY = "Evento della federazione dei pediatri di famiglia."

EXTRACT_SYSTEM = """You extract professional events from an Italian pediatric web page
for a newsletter read by Pediatri di Libera Scelta (PLS).

WHO A PLS IS. A pediatrician running their own outpatient practice in the
territory, following a registered list of children over years: well-child
visits, vaccinations, common acute illness, chronic conditions between
specialist visits, family counselling, referral decisions, practice
organisation. They are NOT hospital pediatricians, not subspecialists, not
emergency or intensive care staff.

EXTRACT ONLY REAL, DATED EVENTS. Congresses, courses, webinars, ECM training.
Ignore news articles, generic pages, past editions with no new date, and
navigation text.

NEVER INVENT. Every field must be present on the page or left empty:
- Do not guess ECM credits, accreditation, fees, deadlines or professions.
- Do not guess the audience. Copy the stated audience verbatim into
  stated_audience. If the page does not say who the event is for, leave it empty.
- If you cannot find a start date, do not output the event at all.
- If you cannot find a link to the event, use the page URL you were given.

pls_fit:
- "explicit" when the page names pediatri di libera scelta, pediatri di
  famiglia, pediatria di famiglia, cure primarie pediatriche, or equivalent.
- "programme" when the audience is not named but concrete programme topics are
  clearly outpatient primary care work.
- "unsupported" when neither holds. Generic pediatric relevance is NOT enough,
  and the promoting society's name is NOT evidence.

why_relevant: one short sentence in Italian, with correct accents, saying what
this event gives a PLS. No marketing language. Leave empty if pls_fit is
"unsupported"."""


class ExtractedEvent(BaseModel):
    title: str
    start_date: str = Field(description="ISO date YYYY-MM-DD")
    end_date: str = ""
    city: str = ""
    region: str = ""
    venue: str = ""
    event_format: str = "unknown"
    promoter: str = ""
    organiser: str = ""
    detail_url: str = ""
    programme_url: str = ""
    stated_audience: str = ""
    programme_evidence: list[str] = Field(default_factory=list)
    pls_fit: str = "unsupported"
    ecm_accredited: bool | None = None
    ecm_credits: str = ""
    accredited_professions: list[str] = Field(default_factory=list)
    registration_status: str = ""
    registration_deadline: str = ""
    early_registration_deadline: str = ""
    fee: str = ""
    is_national_pls_congress: bool = False
    why_relevant: str = ""
    extraction_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ExtractionResponse(BaseModel):
    events: list[ExtractedEvent] = Field(default_factory=list)


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _to_enum(value: str, enum_type: type[EventFormat] | type[PLSFit], default): # type: ignore[no-untyped-def]
    try:
        return enum_type(value.strip().lower())
    except ValueError:
        return default


def to_event(
    raw: ExtractedEvent,
    source_id: str,
    page_url: str,
    source_acronym: str = "",
) -> Event | None:
    """Convert an extracted record, dropping anything that fails the hard rule."""
    start = _parse_date(raw.start_date)
    if start is None or not raw.title.strip():
        return None

    detail_url = raw.detail_url.strip() or page_url
    if not detail_url.startswith("http"):
        return None

    fit = _to_enum(raw.pls_fit, PLSFit, PLSFit.UNSUPPORTED)
    evidence = [e.strip() for e in raw.programme_evidence if e.strip()]
    why = raw.why_relevant.strip()

    # A listing page often names no audience at all. When the promoter is one of
    # the PLS federations, the audience is established by what that federation
    # is, which is why the editorial feedback expects Children 2026 to appear.
    promoter_key = (raw.promoter or source_acronym).strip().lower()
    if fit is PLSFit.UNSUPPORTED and any(
        org in promoter_key or org == source_acronym.strip().lower()
        for org in PLS_ORGANISATIONS
    ):
        fit = PLSFit.EXPLICIT
        evidence = [*evidence, CONSTITUTIONAL_EVIDENCE]
        why = why or CONSTITUTIONAL_WHY

    now = datetime.now(UTC)
    return Event(
        source_id=source_id,
        title=raw.title.strip(),
        promoter=raw.promoter.strip() or source_acronym,
        organiser=raw.organiser.strip(),
        detail_url=detail_url,
        programme_url=raw.programme_url.strip(),
        source_urls=[page_url],
        start_date=start,
        end_date=_parse_date(raw.end_date),
        city=raw.city.strip(),
        region=raw.region.strip(),
        venue=raw.venue.strip(),
        event_format=_to_enum(raw.event_format, EventFormat, EventFormat.UNKNOWN),
        stated_audience=raw.stated_audience.strip(),
        programme_evidence=evidence,
        pls_fit=fit,
        ecm_accredited=raw.ecm_accredited,
        ecm_credits=raw.ecm_credits.strip(),
        accredited_professions=[p.strip() for p in raw.accredited_professions if p.strip()],
        registration_status=raw.registration_status.strip(),
        registration_deadline=_parse_date(raw.registration_deadline),
        early_registration_deadline=_parse_date(raw.early_registration_deadline),
        fee=raw.fee.strip(),
        first_seen_at=now,
        last_seen_at=now,
        extraction_confidence=raw.extraction_confidence,
        is_national_pls_congress=raw.is_national_pls_congress,
        why_relevant=why,
    )


async def extract_events(
    page_text: str,
    page_url: str,
    source_id: str,
    source_name: str,
    client: LLMClient,
    source_acronym: str = "",
) -> list[Event]:
    """Extract dated events from one listing page."""
    if not page_text.strip():
        return []

    prompt = f"""Extract the events listed on this page.

Source: {source_name} ({source_acronym or 'n/a'})
Page URL: {page_url}
Today: {datetime.now(UTC).date().isoformat()}

Page content:
{page_text[:MAX_PAGE_CHARS]}"""

    try:
        resp = await client.complete_structured(
            prompt=prompt,
            response_model=ExtractionResponse,
            system=EXTRACT_SYSTEM,
        )
    except Exception:
        logger.exception("Event extraction failed for %s", page_url)
        return []

    events: list[Event] = []
    for raw in resp.events[:MAX_EVENTS_PER_PAGE]:
        event = to_event(raw, source_id, page_url, source_acronym)
        if event is not None:
            events.append(event)

    logger.info(
        "Extracted %d/%d usable events from %s",
        len(events), len(resp.events), page_url,
    )
    return events
