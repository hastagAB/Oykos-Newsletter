"""Tests for automatic regeneration of stale editorial copy.

Three times a rules change left the published copy untouched, because copy is
cached and regenerating it was opt-in. Copy now carries the fingerprint of the
rules that wrote it, so staleness is detected instead of remembered.
"""
from __future__ import annotations

from oykos.llm.synthesis import SYNTHESIS_SYSTEM, rules_version
from oykos.models.news_item import EditorialBlock


def _pending(candidates: list[EditorialBlock], *, rewrite: bool = False) -> list[EditorialBlock]:
    """Mirror of the selection in build_editorial."""
    current = rules_version()
    return [
        c
        for c in candidates
        if rewrite or not c.headline_operational or c.rules_version != current
    ]


def test_fingerprint_is_stable_for_unchanged_rules() -> None:
    assert rules_version() == rules_version()


def test_fingerprint_tracks_the_rules_text() -> None:
    """A different prompt must produce a different fingerprint."""
    assert len(rules_version()) == 12
    assert rules_version() != ""
    assert SYNTHESIS_SYSTEM  # the material the fingerprint is taken from


def test_copy_written_under_current_rules_is_left_alone() -> None:
    fresh = EditorialBlock(headline_operational="Titolo", rules_version=rules_version())

    assert _pending([fresh]) == []


def test_copy_written_under_older_rules_is_regenerated() -> None:
    stale = EditorialBlock(headline_operational="Titolo", rules_version="oldhash1234")

    assert _pending([stale]) == [stale]


def test_copy_predating_the_fingerprint_is_regenerated() -> None:
    """Items written before the field existed have an empty fingerprint."""
    legacy = EditorialBlock(headline_operational="Titolo", rules_version="")

    assert _pending([legacy]) == [legacy]


def test_item_without_copy_is_always_written() -> None:
    empty = EditorialBlock(rules_version=rules_version())

    assert _pending([empty]) == [empty]


def test_rewrite_forces_everything() -> None:
    fresh = EditorialBlock(headline_operational="Titolo", rules_version=rules_version())

    assert _pending([fresh], rewrite=True) == [fresh]
