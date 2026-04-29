"""Candidate ranker with composition constraints - S016."""
from __future__ import annotations

from oykos.models.news_item import NewsItem
from oykos.models.taxonomy import Geo, Section

# Constraints from scoring.md
MAX_TOTAL = 12
MAX_ITALY = 8
MAX_FOREIGN = 4

SECTION_CAPS: dict[Section, tuple[int, int]] = {
    Section.TOP_PRIORITY: (0, 3),
    Section.CLINICAL: (2, 3),
    Section.REGULATORY: (1, 2),
    Section.DEVICE: (0, 2),
    Section.CME: (1, 2),
}


def assign_section(item: NewsItem) -> Section:
    """Assign item to a newsletter section based on classification."""
    tags = [t.value for t in item.classification.taxonomy_tags]

    # Top priority: safety communications, drug safety, high urgency
    if item.scoring.subscores.urgency >= 4 or "drug_safety" in tags or "device_safety" in tags:
        return Section.TOP_PRIORITY

    # CME
    if "cme_training" in tags or "congresses" in tags:
        return Section.CME

    # Regulatory
    regulatory_tags = {"acn_agreements", "privacy", "telemedicine", "drug_authorization", "drug_shortage"}
    if regulatory_tags.intersection(tags):
        return Section.REGULATORY

    # Device
    if item.classification.device_related or "rapid_tests" in tags or "poct_lab" in tags or "functional_diagnostics" in tags:
        return Section.DEVICE

    # Default: Clinical
    return Section.CLINICAL


def rank_and_select(candidates: list[NewsItem]) -> list[tuple[NewsItem, Section]]:
    """Rank candidates and select top items respecting composition constraints."""
    # Sort by score descending
    sorted_items = sorted(candidates, key=lambda i: i.scoring.score_total, reverse=True)

    # Hard rule: source_trust <= 2 cannot be in top 5
    selected: list[tuple[NewsItem, Section]] = []
    section_counts: dict[Section, int] = {s: 0 for s in Section}
    italy_count = 0
    foreign_count = 0

    for item in sorted_items:
        if len(selected) >= MAX_TOTAL:
            break

        is_italian = item.classification.geo == Geo.IT
        section = assign_section(item)

        # Check geo constraint
        if is_italian and italy_count >= MAX_ITALY:
            continue
        if not is_italian and foreign_count >= MAX_FOREIGN:
            continue

        # Check section cap
        _, cap = SECTION_CAPS.get(section, (0, 3))
        if section_counts[section] >= cap:
            continue

        # Hard rule: low-trust items only if not in top positions
        if item.scoring.subscores.source_trust <= 2 and len(selected) < 5:
            continue

        selected.append((item, section))
        section_counts[section] += 1
        if is_italian:
            italy_count += 1
        else:
            foreign_count += 1

    return selected
