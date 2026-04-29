"""Tests for scoring engine - S013."""
from __future__ import annotations

from oykos.models.news_item import ContentBlock, NewsItem, ScoringBlock, SourceRef, Subscores, Classification
from oykos.models.taxonomy import Geo
from oykos.processing.scoring import (
    apply_penalties,
    compute_raw_score,
    compute_transferability,
    score_item,
)


def _make_item(geo: Geo = Geo.IT, source_key: str = "test") -> NewsItem:
    return NewsItem(
        source=SourceRef(key=source_key, name="Test", source_type="rss", country="IT", reliability_tier=4),
        content=ContentBlock(title="Test", canonical_url="https://example.com/1"),
        classification=Classification(geo=geo),
    )


def test_raw_score_all_fives() -> None:
    sub = Subscores(pls_relevance=5, clinical_impact=5, operational_impact=5,
                    source_trust=5, novelty=5, actionability=5, urgency=5)
    assert compute_raw_score(sub) == 100.0


def test_raw_score_all_zeros() -> None:
    sub = Subscores()
    assert compute_raw_score(sub) == 0.0


def test_raw_score_weighted() -> None:
    sub = Subscores(pls_relevance=5, clinical_impact=0, operational_impact=0,
                    source_trust=0, novelty=0, actionability=0, urgency=0)
    # 5 * 0.22 * 20 = 22.0
    assert abs(compute_raw_score(sub) - 22.0) < 0.01


def test_apply_penalties_duplicate() -> None:
    result = apply_penalties(80.0, ["duplicate"])
    assert result == 70.0


def test_apply_penalties_press_release() -> None:
    result = apply_penalties(50.0, ["press_release"])
    assert result == 30.0


def test_apply_penalties_clamps_to_zero() -> None:
    result = apply_penalties(5.0, ["press_release"])
    assert result == 0.0


def test_apply_penalties_empty() -> None:
    result = apply_penalties(80.0, [])
    assert result == 80.0


def test_transferability_italian() -> None:
    item = _make_item(Geo.IT)
    assert compute_transferability(item) == 1.0


def test_transferability_eu() -> None:
    item = _make_item(Geo.EU)
    assert compute_transferability(item) == 0.85


def test_transferability_global() -> None:
    item = _make_item(Geo.GLOBAL)
    assert compute_transferability(item) == 0.70


def test_transferability_ema_source() -> None:
    item = _make_item(Geo.EU, source_key="ema_alerts")
    assert compute_transferability(item) == 0.95


def test_score_item_full() -> None:
    item = _make_item()
    item.scoring.subscores = Subscores(
        pls_relevance=4, clinical_impact=3, operational_impact=3,
        source_trust=4, novelty=3, actionability=3, urgency=2,
    )
    result = score_item(item)
    assert result.score_total > 0
    assert result.transferability == 1.0
    assert result.score_total <= 100.0
