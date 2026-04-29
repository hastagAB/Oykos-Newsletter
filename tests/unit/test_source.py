"""Tests for oykos.models.source - S002."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from oykos.models.taxonomy import SourceType, TaxonomyTag, Tier


def test_source_creation() -> None:
    from oykos.models.source import FetchConfig, Source

    s = Source(
        key="aifa_safety",
        name="AIFA Safety Communications",
        url="https://www.aifa.gov.it/comunicazioni-di-sicurezza",
        source_type=SourceType.SCRAPE,
        tier=Tier.TIER_1_ITALY,
        reliability=5,
        country="IT",
        category_hints=[TaxonomyTag.DRUG_SAFETY],
        enabled=True,
        fetch_config=FetchConfig(),
    )
    assert s.key == "aifa_safety"
    assert s.tier == Tier.TIER_1_ITALY
    assert s.reliability == 5
    assert s.is_italian


def test_source_is_italian_flag() -> None:
    from oykos.models.source import FetchConfig, Source

    italian = Source(
        key="sip",
        name="SIP",
        url="https://sip.it/feed/",
        source_type=SourceType.RSS,
        tier=Tier.TIER_1_ITALY,
        reliability=4,
        country="IT",
        category_hints=[],
        enabled=True,
        fetch_config=FetchConfig(),
    )
    assert italian.is_italian

    european = Source(
        key="ecdc",
        name="ECDC",
        url="https://ecdc.europa.eu/",
        source_type=SourceType.SCRAPE,
        tier=Tier.TIER_2_EUROPE,
        reliability=5,
        country="EU",
        category_hints=[],
        enabled=True,
        fetch_config=FetchConfig(),
    )
    assert not european.is_italian


def test_source_reliability_range() -> None:
    from oykos.models.source import FetchConfig, Source

    with pytest.raises(ValidationError):
        Source(
            key="bad",
            name="Bad",
            url="https://example.com",
            source_type=SourceType.RSS,
            tier=Tier.RADAR,
            reliability=6,
            country="IT",
            category_hints=[],
            enabled=True,
            fetch_config=FetchConfig(),
        )

    with pytest.raises(ValidationError):
        Source(
            key="bad",
            name="Bad",
            url="https://example.com",
            source_type=SourceType.RSS,
            tier=Tier.RADAR,
            reliability=-1,
            country="IT",
            category_hints=[],
            enabled=True,
            fetch_config=FetchConfig(),
        )


def test_fetch_config_defaults() -> None:
    from oykos.models.source import FetchConfig

    fc = FetchConfig()
    assert fc.timeout_seconds == 30
    assert fc.max_items == 20
    assert fc.custom_headers == {}


def test_source_registry_load() -> None:
    from oykos.models.source import get_source_registry

    registry = get_source_registry()
    assert len(registry) > 30
    # Must have tier 1, 2, 3 and radar
    tiers_present = {s.tier for s in registry.values()}
    assert Tier.TIER_1_ITALY in tiers_present
    assert Tier.TIER_2_EUROPE in tiers_present
    assert Tier.TIER_3_GLOBAL in tiers_present
    assert Tier.RADAR in tiers_present


def test_source_registry_all_enabled() -> None:
    from oykos.models.source import get_source_registry

    registry = get_source_registry()
    for source in registry.values():
        assert source.enabled


def test_source_registry_keys_unique() -> None:
    from oykos.models.source import get_source_registry

    registry = get_source_registry()
    keys = list(registry.keys())
    assert len(keys) == len(set(keys))
