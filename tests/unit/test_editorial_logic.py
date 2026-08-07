"""Editorial logic: scoring, the three selection gates, and noise penalties.

This is the part of the system that decides what a pediatrician does and does not
see. Everything here is deterministic, so it is worth testing directly.
"""
from __future__ import annotations

import pytest

from oykos.models.news_item import (
    Citation,
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import DocumentType, ExclusionReason, Geo, TaxonomyTag
from oykos.processing.gates import evaluate_gates, filter_candidates
from oykos.processing.scoring import (
    apply_penalties,
    compute_raw_score,
    default_applicability,
    detect_penalties,
    score_item,
)


def _item(
    *,
    geo: Geo = Geo.IT,
    source_key: str = "sip",
    country: str = "IT",
    reliability: int = 4,
    doc_type: DocumentType = DocumentType.GUIDELINE,
    tags: list[TaxonomyTag] | None = None,
    title: str = "Aggiornamento",
    raw_text: str = "Contenuto clinico rilevante.",
    url: str = "https://sip.it/articolo",
    citations: list[Citation] | None = None,
    what_to_do: list[str] | None = None,
    **subscores: int,
) -> NewsItem:
    defaults = {
        "pls_relevance": 4,
        "clinical_impact": 4,
        "operational_impact": 3,
        "source_trust": 4,
        "actionability": 4,
    }
    defaults.update(subscores)
    return NewsItem(
        source=SourceRef(
            key=source_key,
            name="Source",
            source_type="rss",
            country=country,
            reliability_tier=reliability,
        ),
        content=ContentBlock(
            title=title, canonical_url=url, raw_text=raw_text, document_type=doc_type,
        ),
        classification=Classification(
            geo=geo,
            taxonomy_tags=[TaxonomyTag.RESPIRATORY] if tags is None else tags,
        ),
        scoring=ScoringBlock(subscores=Subscores(**defaults)),  # type: ignore[arg-type]
        editorial=EditorialBlock(citations=citations or [], what_to_do=what_to_do or []),
    )


# ── Scoring ───────────────────────────────────────────────

def test_all_fives_scores_one_hundred() -> None:
    perfect = Subscores(
        pls_relevance=5, clinical_impact=5, operational_impact=5,
        source_trust=5, novelty=5, actionability=5, urgency=5,
    )
    assert compute_raw_score(perfect) == 100.0


def test_weights_are_applied() -> None:
    """PLS practice relevance is the heaviest criterion at 35%."""
    # pls_relevance is 60% of the practice blend, which carries 35%:
    # 5 * 0.60 * 0.35 * 20 = 21, plus the default applicability 1.0 * 0.10 * 100.
    only_relevance = Subscores(pls_relevance=5)
    assert abs(compute_raw_score(only_relevance) - 31.0) < 0.01


def test_relevance_outweighs_authority() -> None:
    """A trusted source cannot carry a story a PLS cannot use.

    This is the regression guard for the intraosseous-access selection: an
    authoritative hospital item must not outscore a usable primary care one.
    """
    authoritative_but_useless = Subscores(source_trust=5, novelty=5, pls_relevance=0)
    useful_but_modest = Subscores(pls_relevance=5, actionability=4, source_trust=2)

    assert compute_raw_score(useful_but_modest) > compute_raw_score(authoritative_but_useless)


def test_penalties_subtract_and_clamp_at_zero() -> None:
    assert apply_penalties(80.0, ["duplicate"]) == 70.0
    assert apply_penalties(50.0, ["press_release"]) == 30.0
    assert apply_penalties(5.0, ["press_release"]) == 0.0


def test_applicability_fallback_bands() -> None:
    """The deterministic fallback still ranks EU regulatory above US news."""
    assert default_applicability(_item(geo=Geo.IT)) == 1.0
    assert default_applicability(_item(geo=Geo.EU, source_key="ema_news")) == 0.95
    assert default_applicability(_item(geo=Geo.EU, doc_type=DocumentType.GUIDELINE)) == 0.85
    assert default_applicability(_item(geo=Geo.EU, doc_type=DocumentType.STUDY)) == 0.75
    assert default_applicability(
        _item(geo=Geo.GLOBAL, country="US", doc_type=DocumentType.NEWS),
    ) == 0.65


def test_applicability_fallback_stays_in_range() -> None:
    for geo in (Geo.EU, Geo.GLOBAL):
        for country in ("EU", "US", "UK", "JP"):
            assert 0.6 <= default_applicability(_item(geo=geo, country=country)) <= 1.0


def test_score_item_preserves_judged_applicability() -> None:
    """The classifier's judgement survives scoring; it is not overwritten."""
    item = _item(geo=Geo.EU, doc_type=DocumentType.GUIDELINE, transferability=0.42)

    scoring = score_item(item)

    assert scoring.subscores.transferability == 0.42
    assert scoring.transferability == scoring.subscores.transferability


def test_applicability_is_not_applied_twice() -> None:
    """It is a weighted criterion, never also a multiplier on the total."""
    low = score_item(_item(geo=Geo.EU, transferability=0.0)).score_total
    high = score_item(_item(geo=Geo.EU, transferability=1.0)).score_total

    # 10% of the 0-100 scale, and nothing more.
    assert high - low == pytest.approx(10.0, abs=0.5)
    assert 0.0 <= low <= high <= 100.0


# ── Selection gates ───────────────────────────────────────

def test_clean_item_clears_all_three_gates() -> None:
    gating = evaluate_gates(_item())
    assert gating.passed
    assert gating.exclusions == []


def test_gate1_needs_a_tag_and_real_relevance() -> None:
    assert ExclusionReason.NO_PLS_RELEVANCE in evaluate_gates(_item(tags=[])).exclusions
    assert ExclusionReason.NO_PLS_RELEVANCE in evaluate_gates(_item(pls_relevance=1)).exclusions


def test_gate2_rejects_secondary_source_without_a_primary() -> None:
    orphan = _item(reliability=1, url="https://blog.example.com/x", raw_text="Solo opinione.")
    assert ExclusionReason.UNRELIABLE_SOURCE in evaluate_gates(orphan).exclusions


def test_gate2_accepts_secondary_source_that_points_at_a_primary() -> None:
    linked = _item(
        reliability=1,
        url="https://blog.example.com/x",
        raw_text="Come riportato su https://www.aifa.gov.it/comunicazioni-di-sicurezza",
    )
    assert ExclusionReason.UNRELIABLE_SOURCE not in evaluate_gates(linked).exclusions


def test_gate3_rejects_items_with_nothing_to_do() -> None:
    inert = _item(doc_type=DocumentType.NEWS, actionability=0)
    assert ExclusionReason.NOT_ACTIONABLE in evaluate_gates(inert).exclusions


def test_generalist_news_is_excluded() -> None:
    filler = _item(
        doc_type=DocumentType.NEWS, actionability=0, operational_impact=0, clinical_impact=0,
    )
    assert ExclusionReason.GENERALIST_NEWS in evaluate_gates(filler).exclusions


def test_vendor_marketing_is_excluded() -> None:
    promo = _item(
        reliability=0,
        title="Comunicato stampa: nuova gamma di dispositivi",
        raw_text="L'azienda lancia sul mercato la nuova gamma.",
    )
    assert ExclusionReason.VENDOR_MARKETING in evaluate_gates(promo).exclusions


def test_preprint_is_excluded() -> None:
    preprint = _item(raw_text="Questo preprint su medRxiv riporta dati preliminari.")
    gating = evaluate_gates(preprint)
    assert not gating.passed
    assert ExclusionReason.PREPRINT in gating.exclusions


def test_low_trust_source_is_excluded() -> None:
    gating = evaluate_gates(_item(source_trust=2))
    assert not gating.passed
    assert ExclusionReason.UNRELIABLE_SOURCE in gating.exclusions


def test_filter_candidates_keeps_only_survivors() -> None:
    good = _item()
    bad = _item(tags=[], doc_type=DocumentType.NEWS, actionability=0)
    assert filter_candidates([good, bad]) == [good]


# ── Noise penalties ───────────────────────────────────────

def test_penalties_are_detected_together() -> None:
    noisy = _item(
        reliability=1,
        title="Comunicato stampa",
        raw_text="Solo per abbonati. L'azienda annuncia.",
    )
    assert set(detect_penalties(noisy, ["Comunicato stampa"])) == {
        "duplicate", "paywall", "press_release", "single_source",
    }


def test_clean_institutional_item_has_no_penalties() -> None:
    clean = _item(reliability=5, raw_text="Documento istituzionale con dati.")
    assert detect_penalties(clean, []) == []


def test_press_release_with_figures_is_not_penalised() -> None:
    with_data = _item(
        title="Comunicato stampa",
        raw_text="Sensibilita 95% e specificita 92% (n=340).",
        reliability=4,
    )
    assert "press_release" not in detect_penalties(with_data, [])


def test_duplicate_band_sits_below_the_dedup_threshold() -> None:
    """Above the dedup threshold an item is dropped; this band only gets a penalty."""
    from oykos.ingestion.dedup import TITLE_SIMILARITY_THRESHOLD, title_similarity
    from oykos.processing.scoring import DUPLICATE_TITLE_THRESHOLD

    assert DUPLICATE_TITLE_THRESHOLD < TITLE_SIMILARITY_THRESHOLD

    original = "Bronchiolite: aggiornamento delle raccomandazioni"
    rewritten = original
    while title_similarity(original, rewritten) >= TITLE_SIMILARITY_THRESHOLD:
        rewritten += " parola"

    assert "duplicate" in detect_penalties(_item(title=rewritten), [original])
