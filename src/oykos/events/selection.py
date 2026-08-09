"""Event selection - the editorial rules from section 6 of the feedback.

Freshness for an event means proximity to the event date, never publication or
first-seen date. Crawler metadata is monitoring information and must not decide
what a reader sees.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from oykos.events.models import Event, PLSFit

logger = logging.getLogger(__name__)

WINDOW_DAYS = 30
# "A major national PLS congress may appear 60 to 90 days in advance when early
# registration, travel or accommodation planning is useful."
CONGRESS_WINDOW_DAYS = 90
MAX_EVENTS = 4

# Weights for ordering: relevance first, then timing, authority, practical value.
FIT_POINTS = {PLSFit.EXPLICIT: 60.0, PLSFit.PROGRAMME: 35.0, PLSFit.UNSUPPORTED: 0.0}
NATIONAL_CONGRESS_POINTS = 12.0
ECM_POINTS = 8.0
PROGRAMME_EVIDENCE_POINTS = 4.0
MAX_TIMING_POINTS = 20.0


def in_window(event: Event, today: date) -> bool:
    """Whether the event starts inside its eligible window."""
    if event.start_date < today:
        return False
    horizon = CONGRESS_WINDOW_DAYS if event.is_national_pls_congress else WINDOW_DAYS
    return (event.start_date - today).days <= horizon


def score_event(event: Event, today: date) -> float:
    """Rank by PLS relevance first, then timing, authority and practical value."""
    score = FIT_POINTS.get(event.pls_fit, 0.0)

    days_away = max(0, (event.start_date - today).days)
    # Sooner ranks higher, but only after relevance has been accounted for.
    score += MAX_TIMING_POINTS * max(0.0, 1.0 - days_away / CONGRESS_WINDOW_DAYS)

    if event.is_national_pls_congress:
        score += NATIONAL_CONGRESS_POINTS
    if event.ecm_accredited:
        score += ECM_POINTS
    if event.programme_evidence:
        score += PROGRAMME_EVIDENCE_POINTS

    score += event.extraction_confidence * 5.0
    return min(100.0, round(score, 2))


def deduplicate(events: list[Event]) -> list[Event]:
    """Merge the same event arriving from several registry sources.

    The richest record wins and keeps every source URL, so an editor can always
    trace where a claim came from.
    """
    merged: dict[tuple[str, str, str], Event] = {}
    for event in events:
        key = event.dedup_key
        existing = merged.get(key)
        if existing is None:
            merged[key] = event
            continue

        keep, drop = (
            (event, existing)
            if _richness(event) > _richness(existing)
            else (existing, event)
        )
        keep.source_urls = list(dict.fromkeys([*keep.source_urls, *drop.source_urls]))
        if not keep.programme_url:
            keep.programme_url = drop.programme_url
        if not keep.stated_audience:
            keep.stated_audience = drop.stated_audience
        if keep.pls_fit is PLSFit.UNSUPPORTED:
            keep.pls_fit = drop.pls_fit
        merged[key] = keep

    return list(merged.values())


def _richness(event: Event) -> int:
    """How complete a record is, used to pick the survivor of a merge."""
    return sum(
        bool(value)
        for value in (
            event.stated_audience,
            event.programme_url,
            event.city,
            event.ecm_credits,
            event.registration_status,
            event.programme_evidence,
            event.why_relevant,
        )
    )


def select_events(
    events: list[Event],
    today: date,
    max_events: int = MAX_EVENTS,
) -> list[Event]:
    """Apply the window, the audience filter and the cap.

    Returns an empty list rather than filling the section with weak events.
    """
    eligible = [
        event
        for event in deduplicate(events)
        if event.is_publishable
        and event.pls_fit is not PLSFit.UNSUPPORTED
        and in_window(event, today)
    ]

    for event in eligible:
        event.relevance_score = score_event(event, today)

    eligible.sort(key=lambda e: (-e.relevance_score, e.start_date))
    # Relevance decides which events make the cut; the reader reads a diary, so
    # what survives is shown in date order.
    selected = sorted(eligible[:max_events], key=lambda e: e.start_date)

    logger.info(
        "Events: %d extracted, %d eligible, %d selected",
        len(events), len(eligible), len(selected),
    )
    return selected


def next_window_end(today: date) -> date:
    return today + timedelta(days=WINDOW_DAYS)
