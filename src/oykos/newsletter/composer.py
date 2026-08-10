"""Weekly newsletter composer - S022.

Applies the blueprint composition rules in order: selection gates, ranking under
section quotas and the 70/30 Italy/foreign split, risk-based review policy, then
the header furniture (TL;DR, reading time) the reader actually scans first.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from oykos.llm.synthesis import clean_editorial_text
from oykos.models.news_item import (
    IssueMetrics,
    NewsItem,
    Newsletter,
    NewsletterSlot,
    SourceLink,
)
from oykos.models.taxonomy import Geo, IssueStatus, ReviewerRole
from oykos.processing.gates import filter_candidates
from oykos.processing.ranker import MAX_TOTAL, rank_and_select
from oykos.processing.recency import filter_to_week

logger = logging.getLogger(__name__)

WORDS_PER_MINUTE = 200
MIN_READING_MINUTES = 6
MAX_READING_MINUTES = 8
# The opening lists the whole issue: hiding the last item from it made the
# summary disagree with the contents.
TLDR_LINES = 5
MAX_SOURCE_LINKS = 3


def _reading_time(newsletter_words: int) -> int:
    """Reading time in minutes, clamped to the blueprint's 6-8 minute promise."""
    minutes = max(1, round(newsletter_words / WORDS_PER_MINUTE))
    return max(MIN_READING_MINUTES, min(MAX_READING_MINUTES, minutes))


MAX_QUOTE_CHARS = 240
MIN_QUOTE_CHARS = 40


def _pull_quote(item: NewsItem) -> str:
    """The most quotable verbatim passage, for display under attribution.

    Quoting a short passage with credit is defensible; it also lets the reader
    see the source's own wording rather than only our paraphrase.
    """
    for passage in item.content.key_passages:
        quote = " ".join(passage.quote.split())
        if MIN_QUOTE_CHARS <= len(quote) <= MAX_QUOTE_CHARS:
            return quote
    return ""


def _source_links(item: NewsItem) -> list[SourceLink]:
    """The 2-3 source links the blueprint requires under every item."""
    links: list[SourceLink] = [
        SourceLink(label=item.source.name, url=item.content.canonical_url),
    ]
    seen = {item.content.canonical_url}
    for citation in item.editorial.citations:
        if not citation.source_url or citation.source_url in seen:
            continue
        seen.add(citation.source_url)
        links.append(SourceLink(label="Fonte primaria", url=citation.source_url))
        if len(links) >= MAX_SOURCE_LINKS:
            break
    return links


def _tldr(slots: list[NewsletterSlot]) -> list[str]:
    """The week's conclusions, one line each.

    This used to reprint ``why_it_matters`` verbatim, so every reader read the
    same paragraph twice - exactly the padding section 8 forbids. The headline
    already states the conclusion, and repeating it here is the second reading
    level section 4 asks for rather than duplicated prose.
    """
    lines: list[str] = []
    for slot in slots:
        line = slot.editorial.headline_operational.strip()
        if line and line not in lines:
            lines.append(line)
        if len(lines) == TLDR_LINES:
            break
    return lines


def compose_newsletter(
    candidates: list[NewsItem],
    week: str,
    title: str = "L'Essenziale in Pediatria",
    max_total: int = MAX_TOTAL,
) -> Newsletter:
    """Compose a newsletter from candidate items."""
    # Blocked items never reach the reader, whatever their score.
    publishable = [item for item in candidates if not item.editorial.blocked]

    # Gate 1/2/3 plus exclusion criteria.
    eligible = filter_candidates(publishable)

    # Recency outranks filling the layout: only this week's publications ship,
    # and an undated source cannot be verified so it cannot be included.
    before_recency = len(eligible)
    eligible = filter_to_week(eligible, week)
    if before_recency != len(eligible):
        logger.info(
            "Recency filter kept %d of %d candidates for %s",
            len(eligible), before_recency, week,
        )

    # A headline is required to render the item. An action is NOT: "il dato e'
    # interessante, ma non modifica da solo la pratica" is a valid conclusion,
    # and requiring what_to_do here would silently delete exactly those items.
    eligible = [item for item in eligible if item.editorial.headline_operational]

    selected = rank_and_select(eligible, max_total=max_total)

    # An issue is 12 items; an editor reads all of them. No sampling policy.
    for item, _ in selected:
        clean_editorial_text(item.editorial)
        item.editorial.review.needs_human_review = True
        item.editorial.review.reviewer_role = ReviewerRole.MEDICAL_EDITOR.value

    slots: list[NewsletterSlot] = []
    section_counts: dict[str, int] = {}
    italy_count = 0
    foreign_count = 0
    word_count = 0

    for position, (item, section) in enumerate(selected, start=1):
        slots.append(
            NewsletterSlot(
                position=position,
                section=section,
                item_id=item.item_id,
                editorial=item.editorial,
                source_name=item.source.name,
                source_url=item.content.canonical_url,
                evidence_quote=_pull_quote(item),
                access_limited=item.content.access_limited,
                source_links=_source_links(item),
            ),
        )

        section_counts[section.value] = section_counts.get(section.value, 0) + 1
        if item.classification.geo == Geo.IT:
            italy_count += 1
        else:
            foreign_count += 1

        word_count += len(
            " ".join(
                [
                    item.editorial.headline_operational,
                    item.editorial.what_emerges,
                    item.editorial.why_it_matters,
                    item.editorial.summary,
                    *item.editorial.what_to_do,
                ],
            ).split(),
        )

    newsletter = Newsletter(
        issue_id=uuid4(),
        week=week,
        created_at=datetime.now(UTC),
        slots=slots,
        tldr=_tldr(slots),
        reading_time_minutes=_reading_time(word_count),
        status=IssueStatus.DRAFT,
        metrics=IssueMetrics(
            italy_count=italy_count,
            foreign_count=foreign_count,
            section_counts=section_counts,
        ),
    )

    logger.info(
        "Composed newsletter %s for '%s': %d items (%d IT / %d foreign), %d min read",
        week,
        title,
        len(slots),
        italy_count,
        foreign_count,
        newsletter.reading_time_minutes,
    )
    return newsletter
