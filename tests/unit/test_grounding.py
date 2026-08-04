"""Grounding: evidence extraction and claim verification.

Source -> claim traceability is the first non-negotiable principle of the
product. These tests pin the two mechanisms that enforce it: a quote must
actually appear in the source, and an ungrounded item must be refused.
"""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from oykos.llm.extraction import ExtractedPassage, ExtractionResponse, extract_key_passages
from oykos.llm.verification import VerificationResult, verify_claims
from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    KeyPassage,
    NewsItem,
    SourceRef,
)
from oykos.models.taxonomy import Confidence, TaxonomyTag

SOURCE_TEXT = (
    "AIFA comunica il richiamo dei lotti interessati. "
    "I pediatri devono verificare le confezioni in studio."
)
REAL_QUOTE = "AIFA comunica il richiamo dei lotti interessati."


class FakeClient:
    """Stands in for LLMClient, returning canned structured responses."""

    def __init__(self, responses: list[Any] | None = None, raises: bool = False) -> None:
        self._responses = list(responses or [])
        self._raises = raises

    async def complete_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        system: str = "",
        model: str | None = None,
        max_output_tokens: int = 0,
    ) -> Any:
        if self._raises:
            raise RuntimeError("upstream failure")
        return self._responses.pop(0)


def _item(raw_text: str = SOURCE_TEXT, passages: list[KeyPassage] | None = None) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key="aifa_safety", name="AIFA", source_type="scrape",
            country="IT", reliability_tier=5,
        ),
        content=ContentBlock(
            title="Richiamo lotti",
            canonical_url="https://www.aifa.gov.it/x",
            raw_text=raw_text,
            key_passages=passages or [],
        ),
        classification=Classification(taxonomy_tags=[TaxonomyTag.DRUG_SAFETY]),
    )


# ── Evidence extraction ───────────────────────────────────

@pytest.mark.asyncio
async def test_paraphrased_passages_are_discarded() -> None:
    """A quote that is not in the source is a hallucination, not evidence."""
    client = FakeClient([
        ExtractionResponse(passages=[
            ExtractedPassage(quote=REAL_QUOTE),
            ExtractedPassage(quote="Sono stati segnalati numerosi decessi."),
        ]),
    ])

    passages = await extract_key_passages(_item(), client)  # type: ignore[arg-type]

    assert [p.quote for p in passages] == [REAL_QUOTE]


@pytest.mark.asyncio
async def test_extraction_degrades_quietly() -> None:
    assert await extract_key_passages(_item(raw_text=""), FakeClient()) == []  # type: ignore[arg-type]
    assert await extract_key_passages(_item(), FakeClient(raises=True)) == []  # type: ignore[arg-type]


# ── Verification ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_an_item_with_no_evidence_is_blocked() -> None:
    editorial = EditorialBlock(summary="Qualcosa", confidence=Confidence.HIGH)

    result = await verify_claims(editorial, _item(), FakeClient())  # type: ignore[arg-type]

    assert result.blocked
    assert result.confidence is Confidence.LOW


@pytest.mark.asyncio
async def test_multiple_unsupported_claims_block_the_item() -> None:
    item = _item(passages=[KeyPassage(quote=REAL_QUOTE)])
    client = FakeClient([
        VerificationResult(
            verified=False,
            unsupported_claims=["claim uno", "claim due"],
            adjusted_confidence="low",
        ),
    ])

    result = await verify_claims(
        EditorialBlock(summary="Qualcosa"), item, client,  # type: ignore[arg-type]
    )

    assert result.blocked


@pytest.mark.asyncio
async def test_a_single_unsupported_claim_only_downgrades() -> None:
    item = _item(passages=[KeyPassage(quote=REAL_QUOTE)])
    client = FakeClient([
        VerificationResult(
            verified=False, unsupported_claims=["claim uno"], adjusted_confidence="medium",
        ),
    ])

    result = await verify_claims(
        EditorialBlock(summary="Qualcosa", confidence=Confidence.HIGH),
        item,
        client,  # type: ignore[arg-type]
    )

    assert not result.blocked
    assert result.confidence is Confidence.LOW
    assert result.review.needs_human_review


@pytest.mark.asyncio
async def test_a_fully_grounded_item_ships() -> None:
    item = _item(passages=[KeyPassage(quote=REAL_QUOTE)])
    client = FakeClient([
        VerificationResult(verified=True, unsupported_claims=[], adjusted_confidence="high"),
    ])

    result = await verify_claims(
        EditorialBlock(summary="Qualcosa"), item, client,  # type: ignore[arg-type]
    )

    assert not result.blocked
    assert result.confidence is Confidence.HIGH
