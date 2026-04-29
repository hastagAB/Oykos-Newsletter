"""Weekly newsletter composer - S022."""
from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from oykos.models.news_item import (
    EditorialBlock,
    IssueMetrics,
    Newsletter,
    NewsItem,
    NewsletterSlot,
)
from oykos.models.taxonomy import Geo, IssueStatus, Section
from oykos.processing.ranker import rank_and_select

logger = logging.getLogger(__name__)

# Section display order (highest priority first)
SECTION_ORDER: list[Section] = [
    Section.TOP_PRIORITY,
    Section.CLINICAL,
    Section.REGULATORY,
    Section.DEVICE,
    Section.CME,
]


def compose_newsletter(
    candidates: list[NewsItem],
    week: str,
    title: str = "L'Essenziale in Pediatria",
) -> Newsletter:
    """Compose a newsletter from ranked candidate items."""
    selected = rank_and_select(candidates)

    # Filter out items without valid editorial content
    selected = [
        (item, section) for item, section in selected
        if item.editorial.headline_operational and item.editorial.what_to_do
    ]

    # Sort by section priority, then by score within each section
    section_rank = {s: i for i, s in enumerate(SECTION_ORDER)}
    selected.sort(key=lambda pair: (
        section_rank.get(pair[1], len(SECTION_ORDER)),
        -pair[0].scoring.score_total,
    ))

    slots: list[NewsletterSlot] = []
    section_counts: dict[str, int] = {}
    italy_count = 0
    foreign_count = 0

    for position, (item, section) in enumerate(selected, start=1):
        slot = NewsletterSlot(
            position=position,
            section=section,
            item_id=item.item_id,
            editorial=item.editorial,
            source_name=item.source.name,
            source_url=item.content.canonical_url,
        )
        slots.append(slot)

        section_name = section.value
        section_counts[section_name] = section_counts.get(section_name, 0) + 1

        if item.classification.geo == Geo.IT:
            italy_count += 1
        else:
            foreign_count += 1

    metrics = IssueMetrics(
        italy_count=italy_count,
        foreign_count=foreign_count,
        section_counts=section_counts,
    )

    newsletter = Newsletter(
        issue_id=uuid4(),
        week=week,
        created_at=datetime.utcnow(),
        slots=slots,
        status=IssueStatus.DRAFT,
        metrics=metrics,
    )

    logger.info(
        "Composed newsletter %s: %d items (%d IT / %d foreign)",
        week, len(slots), italy_count, foreign_count,
    )
    return newsletter
