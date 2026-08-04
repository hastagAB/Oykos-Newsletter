"""Tests for the blueprint newsletter structure end to end.

Covers the composition rules (section quotas, 70/30 split) and the 5-block item
template that the reader actually sees.
"""
from __future__ import annotations

from collections import Counter

from oykos.models.news_item import (
    Citation,
    Classification,
    ContentBlock,
    EditorialBlock,
    KeyPassage,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    Geo,
    TaxonomyTag,
)
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.template import (
    CTA_TITLE,
    CTA_URL,
    DISCLAIMER,
    render_html,
    render_plain_text,
)
from oykos.processing.ranker import MAX_ITALY, MAX_PER_SOURCE, MAX_TOTAL, SECTION_QUOTAS

WEEK = "2026-W17"


def _make_item(
    *,
    tags: list[TaxonomyTag],
    score: float,
    geo: Geo = Geo.IT,
    source_trust: int = 4,
    urgency: int = 2,
    device_related: bool = False,
    confidence: Confidence = Confidence.HIGH,
    citations: list[Citation] | None = None,
    why: str | None = None,
    source_key: str | None = None,
) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            # Distinct per item by default: real issues draw on many sources, and
            # the ranker caps how many slots any one of them can take.
            key=source_key or f"src-{tags[0].value}-{score}",
            name=source_key or "Fonte Istituzionale",
            source_type="rss",
            country="IT" if geo is Geo.IT else "EU",
            reliability_tier=source_trust,
        ),
        content=ContentBlock(
            title="Titolo",
            canonical_url=f"https://esempio.it/{tags[0].value}-{score}",
            raw_text="Testo di riferimento.",
            document_type=DocumentType.GUIDELINE,
        ),
        classification=Classification(
            geo=geo,
            taxonomy_tags=tags,
            device_related=device_related,
        ),
        scoring=ScoringBlock(
            score_total=score,
            subscores=Subscores(
                pls_relevance=4,
                actionability=4,
                clinical_impact=4,
                operational_impact=3,
                source_trust=source_trust,
                urgency=urgency,
            ),
        ),
        editorial=EditorialBlock(
            headline_operational="Verificare i lotti interessati",
            why_it_matters=why or f"Riduce il rischio clinico in ambulatorio ({score}).",
            what_to_do=["Controllare i lotti", "Informare i genitori"],
            summary="Dettaglio clinico e operativo su cosa cambia in studio.",
            confidence=confidence,
            citations=citations or [],
        ),
    )


def _full_candidate_pool() -> list[NewsItem]:
    """A realistic week: enough Italian and foreign material in every section."""
    items: list[NewsItem] = []
    # Italian: top priority, clinical, regulatory, device, CME
    for i in range(4):
        items.append(_make_item(tags=[TaxonomyTag.DRUG_SAFETY], score=95 - i, urgency=5))
    for i in range(4):
        items.append(_make_item(tags=[TaxonomyTag.RESPIRATORY], score=80 - i))
    for i in range(3):
        items.append(_make_item(tags=[TaxonomyTag.ACN_AGREEMENTS], score=70 - i))
    for i in range(3):
        items.append(
            _make_item(tags=[TaxonomyTag.RAPID_TESTS], score=60 - i, device_related=True),
        )
    for i in range(3):
        items.append(_make_item(tags=[TaxonomyTag.CME_TRAINING], score=50 - i))
    # Foreign transferable, spread across sections so the 30% share is fillable.
    items.append(_make_item(tags=[TaxonomyTag.DEVICE_SAFETY], score=93, geo=Geo.EU, urgency=5))
    items.append(_make_item(tags=[TaxonomyTag.SURVEILLANCE], score=79, geo=Geo.EU))
    items.append(_make_item(tags=[TaxonomyTag.DRUG_AUTHORIZATION], score=69, geo=Geo.EU))
    items.append(
        _make_item(
            tags=[TaxonomyTag.FUNCTIONAL_DIAGNOSTICS],
            score=59,
            geo=Geo.EU,
            device_related=True,
        ),
    )
    items.append(_make_item(tags=[TaxonomyTag.CONGRESSES], score=49, geo=Geo.EU))
    return items


def test_issue_never_exceeds_the_slot_limit() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    assert len(newsletter.slots) <= MAX_TOTAL


def test_no_single_source_dominates_an_issue() -> None:
    """A pediatric reviewer flagged "c'e troppa SIP": one society must not own an issue."""
    pool = [
        _make_item(tags=[TaxonomyTag.RESPIRATORY], score=90 - i, source_key="sip")
        for i in range(6)
    ]
    pool += [
        _make_item(tags=[TaxonomyTag.ACN_AGREEMENTS], score=70, source_key="sisac"),
        _make_item(tags=[TaxonomyTag.DRUG_SAFETY], score=95, source_key="aifa", urgency=5),
        _make_item(tags=[TaxonomyTag.RAPID_TESTS], score=60, source_key="choosing_wisely"),
    ]

    newsletter = compose_newsletter(pool, WEEK)
    counts = Counter(slot.source_name for slot in newsletter.slots)

    assert counts["sip"] <= MAX_PER_SOURCE
    assert max(counts.values()) <= MAX_PER_SOURCE


def test_section_quotas_are_respected() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    counts = newsletter.metrics.section_counts

    for section, quota in SECTION_QUOTAS.items():
        assert counts.get(section.value, 0) <= quota.maximum


def test_italy_foreign_split_is_enforced_on_final_slots() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    assert newsletter.metrics.italy_count <= MAX_ITALY
    assert newsletter.metrics.foreign_count <= 4


def test_blocked_items_never_reach_the_reader() -> None:
    pool = _full_candidate_pool()
    blocked = _make_item(tags=[TaxonomyTag.DRUG_SAFETY], score=100, urgency=5)
    blocked.editorial.blocked = True
    pool.append(blocked)

    newsletter = compose_newsletter(pool, WEEK)
    assert blocked.item_id not in {slot.item_id for slot in newsletter.slots}


def test_tldr_has_three_lines() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    assert len(newsletter.tldr) == 3


def test_reading_time_within_promised_range() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    assert 6 <= newsletter.reading_time_minutes <= 8


def test_source_links_include_primary_citation() -> None:
    pool = [
        _make_item(
            tags=[TaxonomyTag.DRUG_SAFETY],
            score=90,
            urgency=5,
            citations=[Citation(claim_id="c1", source_url="https://www.aifa.gov.it/x")],
        ),
    ]
    newsletter = compose_newsletter(pool, WEEK)
    urls = [link.url for link in newsletter.slots[0].source_links]

    assert "https://www.aifa.gov.it/x" in urls
    assert 1 <= len(urls) <= 3


def test_html_renders_the_five_blocks() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    newsletter.preheader = "Anteprima della settimana"
    html = render_html(newsletter, unsubscribe_url="https://x.it/u")

    assert "Verificare i lotti interessati" in html          # 1 headline
    assert "Riduce il rischio clinico" in html                # 2 why it matters
    assert "Cosa fare / cosa evitare" in html                 # 3 do/avoid
    assert "Dettaglio clinico e operativo" in html            # 4 detail
    assert "Fonti" in html                                    # 5 sources
    assert "Affidabilità HIGH" in html                        # confidence badge


def test_html_includes_header_furniture_and_disclaimer() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    newsletter.preheader = "Anteprima della settimana"
    html = render_html(
        newsletter,
        unsubscribe_url="https://x.it/u",
        preferences_url="https://x.it/p",
        archive_url="https://x.it/a",
    )

    assert "Anteprima della settimana" in html
    assert "Cosa cambia davvero questa settimana" in html
    assert "lettura" in html
    assert "https://x.it/u" in html
    assert "https://x.it/p" in html
    assert DISCLAIMER[:40] in html


def test_html_escapes_source_content() -> None:
    pool = [_make_item(tags=[TaxonomyTag.DRUG_SAFETY], score=90, urgency=5)]
    pool[0].editorial.headline_operational = "<script>alert('xss')</script>"

    html = render_html(compose_newsletter(pool, WEEK))

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_plain_text_contains_detail_sources_and_disclaimer() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)
    text = render_plain_text(newsletter, unsubscribe_url="https://x.it/u")

    assert "COSA CAMBIA DAVVERO QUESTA SETTIMANA" in text
    assert "Dettaglio clinico e operativo" in text
    assert "Fonti:" in text
    assert DISCLAIMER[:40] in text
    assert "https://x.it/u" in text


def test_empty_candidates_produce_empty_issue() -> None:
    newsletter = compose_newsletter([], WEEK)
    assert newsletter.slots == []
    assert newsletter.tldr == []


def test_closing_cta_appears_in_both_renderings() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)

    html = render_html(newsletter)
    text = render_plain_text(newsletter)

    assert CTA_TITLE in html
    assert CTA_URL in html
    assert CTA_TITLE in text
    assert CTA_URL in text


def test_read_online_link_appears_only_when_the_issue_is_published() -> None:
    newsletter = compose_newsletter(_full_candidate_pool(), WEEK)

    assert "Leggi online" not in render_html(newsletter)

    newsletter.public_url = "https://oykomed.it/briefing-2026-w17"
    published = render_html(newsletter)

    assert "Leggi online" in published
    assert "https://oykomed.it/briefing-2026-w17" in published


def test_pull_quote_is_verbatim_and_attributed() -> None:
    """We quote the source with credit rather than republishing its imagery."""
    quote = (
        "La saturimetria domiciliare non e raccomandata di routine nel lattante "
        "con bronchiolite lieve gestito a domicilio."
    )
    item = _make_item(tags=[TaxonomyTag.RESPIRATORY], score=90)
    item.content.key_passages = [KeyPassage(quote=quote, url=item.content.canonical_url)]

    newsletter = compose_newsletter([item], WEEK)
    html = render_html(newsletter)

    assert newsletter.slots[0].evidence_quote == quote
    assert quote in html
    # The attribution has to travel with the quote.
    assert newsletter.slots[0].source_name in html
    assert quote in render_plain_text(newsletter)


def test_pull_quote_is_omitted_when_no_passage_is_quotable() -> None:
    item = _make_item(tags=[TaxonomyTag.RESPIRATORY], score=90)
    item.content.key_passages = [KeyPassage(quote="Troppo corto.")]

    newsletter = compose_newsletter([item], WEEK)

    assert newsletter.slots[0].evidence_quote == ""
