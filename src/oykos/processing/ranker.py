"""Candidate ranker with composition constraints.

Up to 5 slots, but no section minimums: the editorial guidelines forbid
stretching content to fill a fixed layout, so an issue is as long as the week
was. Two strong stories beat three average ones.

Geography does not decide selection. An item earns its slot on relevance to PLS
practice; Italian applicability is one weighted criterion inside the score, not
a quota. The only structural cap left is at most 2 items from a single source,
so no one society can dominate an issue.
"""
from __future__ import annotations

from dataclasses import dataclass

from oykos.models.news_item import NewsItem
from oykos.models.taxonomy import Section

MAX_TOTAL = 5
# One source dominating an issue reads as a press office, not a briefing.
MAX_PER_SOURCE = 2
HIGH_URGENCY = 4


@dataclass(frozen=True)
class SectionQuota:
    minimum: int
    maximum: int


SECTION_QUOTAS: dict[Section, SectionQuota] = {
    Section.TOP_PRIORITY: SectionQuota(minimum=0, maximum=2),
    Section.CLINICAL: SectionQuota(minimum=0, maximum=2),
    Section.REGULATORY: SectionQuota(minimum=0, maximum=1),
    Section.DEVICE: SectionQuota(minimum=0, maximum=1),
    Section.CME: SectionQuota(minimum=0, maximum=1),
    # Events are selected by their own pipeline, never by the news ranker.
    Section.EVENTS: SectionQuota(minimum=0, maximum=0),
}

# Section order is also the display order in the rendered newsletter.
SECTION_ORDER: list[Section] = [
    Section.TOP_PRIORITY,
    Section.CLINICAL,
    Section.REGULATORY,
    Section.DEVICE,
    Section.CME,
]

TOP_PRIORITY_TAGS = frozenset({"drug_safety", "device_safety"})
CME_TAGS = frozenset({"cme_training", "congresses"})
REGULATORY_TAGS = frozenset({
    "acn_agreements",
    "privacy",
    "telemedicine",
    "drug_authorization",
    "drug_shortage",
})
DEVICE_TAGS = frozenset({
    "rapid_tests",
    "poct_lab",
    "functional_diagnostics",
    "screening",
    "ai_digital_health",
})


def assign_section(item: NewsItem) -> Section:
    """Assign an item to a newsletter section based on its classification."""
    tags = {t.value for t in item.classification.taxonomy_tags}

    if item.scoring.subscores.urgency >= HIGH_URGENCY or TOP_PRIORITY_TAGS & tags:
        return Section.TOP_PRIORITY
    if CME_TAGS & tags:
        return Section.CME
    if REGULATORY_TAGS & tags:
        return Section.REGULATORY
    if item.classification.device_related or DEVICE_TAGS & tags:
        return Section.DEVICE
    return Section.CLINICAL


class _Composition:
    """Bookkeeping for the slot constraints during selection."""

    def __init__(self, max_total: int) -> None:
        self.max_total = max_total
        self.selected: list[tuple[NewsItem, Section]] = []
        self.section_counts: dict[Section, int] = dict.fromkeys(Section, 0)
        self.source_counts: dict[str, int] = {}

    @property
    def is_full(self) -> bool:
        return len(self.selected) >= self.max_total

    def can_take(self, item: NewsItem, section: Section) -> bool:
        if self.is_full:
            return False
        if self.section_counts[section] >= SECTION_QUOTAS[section].maximum:
            return False
        return self.source_counts.get(item.source.key, 0) < MAX_PER_SOURCE

    def take(self, item: NewsItem, section: Section) -> None:
        self.selected.append((item, section))
        self.section_counts[section] += 1
        self.source_counts[item.source.key] = self.source_counts.get(item.source.key, 0) + 1


def rank_and_select(
    candidates: list[NewsItem],
    max_total: int = MAX_TOTAL,
) -> list[tuple[NewsItem, Section]]:
    """Rank candidates and select the final slots.

    Two passes, so section quotas beat raw score: fill every section to its
    minimum first, then spend what is left on the highest scoring items.
    """
    ranked = sorted(candidates, key=lambda i: i.scoring.score_total, reverse=True)
    assignments = [(item, assign_section(item)) for item in ranked]
    composition = _Composition(max_total)
    taken: set[int] = set()

    def consume(section_filter: Section | None = None, *, respect_minimum: bool = False) -> None:
        for index, (item, section) in enumerate(assignments):
            if index in taken or composition.is_full:
                continue
            if section_filter is not None and section is not section_filter:
                continue
            if respect_minimum and (
                composition.section_counts[section] >= SECTION_QUOTAS[section].minimum
            ):
                continue
            if composition.can_take(item, section):
                composition.take(item, section)
                taken.add(index)

    for section in SECTION_ORDER:
        consume(section, respect_minimum=True)
    consume()

    section_rank = {section: i for i, section in enumerate(SECTION_ORDER)}
    composition.selected.sort(
        key=lambda pair: (section_rank[pair[1]], -pair[0].scoring.score_total),
    )
    return composition.selected
