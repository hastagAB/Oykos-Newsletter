"""Tests for the PLS events section - editorial feedback section 6.

The rules under test are the ones that protect the reader: an event is chosen
because it is upcoming and demonstrably for a PLS, never because its page was
published this week, and never on the strength of the promoting society's name.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from oykos.events.models import Event, EventFormat, PLSFit
from oykos.events.selection import (
    MAX_EVENTS,
    deduplicate,
    in_window,
    score_event,
    select_events,
)
from oykos.newsletter.template import event_view, format_event_dates

TODAY = date(2026, 8, 7)


def _event(
    *,
    title: str = "Children 2026",
    days_ahead: int = 14,
    fit: PLSFit = PLSFit.EXPLICIT,
    city: str = "Bari",
    congress: bool = False,
    **extra: object,
) -> Event:
    return Event(
        title=title,
        detail_url="https://fimp.pro/children-2026",
        start_date=TODAY + timedelta(days=days_ahead),
        city=city,
        pls_fit=fit,
        is_national_pls_congress=congress,
        **extra,  # type: ignore[arg-type]
    )


# ── The window ────────────────────────────────────────────

def test_event_inside_thirty_days_is_eligible() -> None:
    assert in_window(_event(days_ahead=29), TODAY) is True


def test_event_beyond_thirty_days_waits_for_a_later_issue() -> None:
    """The feedback's own example: Naples on 12 September, outside W32."""
    assert in_window(_event(days_ahead=36), TODAY) is False


def test_past_event_is_never_eligible() -> None:
    assert in_window(_event(days_ahead=-1), TODAY) is False


def test_event_starting_today_is_still_eligible() -> None:
    assert in_window(_event(days_ahead=0), TODAY) is True


def test_national_congress_may_appear_up_to_ninety_days_out() -> None:
    """Early notice exists so travel and registration can be planned."""
    assert in_window(_event(days_ahead=75, congress=True), TODAY) is True
    assert in_window(_event(days_ahead=75, congress=False), TODAY) is False


def test_congress_exception_still_has_a_limit() -> None:
    assert in_window(_event(days_ahead=120, congress=True), TODAY) is False


# ── The audience filter ───────────────────────────────────

def test_unsupported_audience_is_excluded() -> None:
    """Generic pediatric relevance is not enough."""
    selected = select_events([_event(fit=PLSFit.UNSUPPORTED)], TODAY)

    assert selected == []


def test_explicit_audience_outranks_programme_inference() -> None:
    explicit = _event(title="Esplicito", fit=PLSFit.EXPLICIT)
    inferred = _event(title="Dedotto", fit=PLSFit.PROGRAMME)

    assert score_event(explicit, TODAY) > score_event(inferred, TODAY)


def test_relevance_beats_timing() -> None:
    """Ordering is relevance first, then timing."""
    soon_but_weak = _event(title="Vicino", days_ahead=2, fit=PLSFit.PROGRAMME)
    later_but_explicit = _event(title="Esplicito", days_ahead=25, fit=PLSFit.EXPLICIT)

    selected = select_events([soon_but_weak, later_but_explicit], TODAY)

    assert [e.title for e in selected] == ["Esplicito", "Vicino"]


# ── Publishability ────────────────────────────────────────

def test_event_without_official_url_is_not_publishable() -> None:
    event = _event()
    event.detail_url = ""

    assert event.is_publishable is False
    assert select_events([event], TODAY) == []


def test_publishable_requires_supported_audience() -> None:
    assert _event(fit=PLSFit.UNSUPPORTED).is_publishable is False
    assert _event(fit=PLSFit.PROGRAMME).is_publishable is True


# ── Deduplication ─────────────────────────────────────────

def test_same_event_from_two_sources_is_merged() -> None:
    first = _event()
    first.source_urls = ["https://sip.it/patrocinati"]
    second = _event(stated_audience="Pediatri di libera scelta")
    second.source_urls = ["https://fimp.pro/eventi"]

    merged = deduplicate([first, second])

    assert len(merged) == 1
    assert len(merged[0].source_urls) == 2


def test_merge_keeps_the_richer_record() -> None:
    thin = _event()
    rich = _event(stated_audience="Pediatri di famiglia", ecm_credits="8")

    merged = deduplicate([thin, rich])

    assert merged[0].stated_audience == "Pediatri di famiglia"


def test_different_cities_are_different_events() -> None:
    assert len(deduplicate([_event(city="Bari"), _event(city="Napoli")])) == 2


# ── The cap ───────────────────────────────────────────────

def test_section_is_capped() -> None:
    many = [_event(title=f"Evento {i}", days_ahead=i + 1) for i in range(10)]

    assert len(select_events(many, TODAY)) == MAX_EVENTS


def test_no_strong_matches_means_no_section() -> None:
    """Better an absent section than one padded with weak events."""
    assert select_events([], TODAY) == []
    assert select_events([_event(days_ahead=200)], TODAY) == []


# ── Crawler metadata must not filter ──────────────────────

def test_first_seen_date_does_not_affect_selection() -> None:
    """Freshness for an event means proximity to the event, not to discovery."""
    long_known = _event()
    long_known.first_seen_at = datetime(2026, 1, 1)  # noqa: DTZ001 - naive UTC
    long_known.last_seen_at = datetime(2026, 1, 1)  # noqa: DTZ001 - naive UTC

    assert select_events([long_known], TODAY) != []


# ── Reader-facing output ──────────────────────────────────

def test_same_month_range_is_collapsed() -> None:
    assert format_event_dates(date(2026, 9, 4), date(2026, 9, 5)) == "4-5 settembre"


def test_single_day_has_no_range() -> None:
    assert format_event_dates(date(2026, 9, 4), None) == "4 settembre"


def test_cross_month_range_names_both_months() -> None:
    result = format_event_dates(date(2026, 8, 30), date(2026, 9, 2))

    assert result == "30 agosto - 2 settembre"


def test_online_event_shows_online_not_a_city() -> None:
    event = _event(city="Roma", event_format=EventFormat.ONLINE)

    assert event_view(event)["where"] == "Online"


def test_ecm_is_only_shown_when_stated() -> None:
    """Never invent accreditation."""
    assert event_view(_event())["ecm"] == ""
    assert event_view(_event(ecm_accredited=True, ecm_credits="8"))["ecm"] == "ECM 8"


def test_programme_link_is_preferred_when_available() -> None:
    event = _event(programme_url="https://fimp.pro/programma.pdf")

    assert event_view(event)["url"] == "https://fimp.pro/programma.pdf"


@pytest.mark.parametrize("field", ["title", "when", "url"])
def test_view_always_carries_the_decision_fields(field: str) -> None:
    assert event_view(_event())[field]
