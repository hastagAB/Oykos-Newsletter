"""The subject and preheader must not generalise one item's conclusion.

A regulatory notice that changes practice sitting alongside three observational
studies used to license "cosa cambia questa settimana" as the frame for the
whole issue, which misrepresents the other three.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from oykos.models.news_item import EditorialBlock, Newsletter, NewsletterSlot
from oykos.models.taxonomy import ImplicationKind, Section
from oykos.newsletter.subject import SubjectResponse, generate_subject_line


def _slot(position: int, kind: ImplicationKind, source: str) -> NewsletterSlot:
    return NewsletterSlot(
        position=position,
        section=Section.CLINICAL,
        item_id=uuid4(),
        source_name=source,
        editorial=EditorialBlock(
            headline_operational=f"Titolo {position}",
            implication_kind=kind,
        ),
    )


class _CapturingClient:
    """Records the prompt so the instruction given to the writer can be asserted."""

    def __init__(self) -> None:
        self.prompt = ""

    async def complete_structured(self, **kwargs: Any) -> SubjectResponse:
        self.prompt = kwargs["prompt"]
        return SubjectResponse(subject="Oggetto", preheader="Anteprima")


async def _prompt_for(*kinds: ImplicationKind) -> str:
    newsletter = Newsletter(
        week="2026-W32",
        slots=[_slot(i + 1, k, f"Fonte {i + 1}") for i, k in enumerate(kinds)],
    )
    client = _CapturingClient()
    await generate_subject_line(newsletter, client)  # type: ignore[arg-type]
    return client.prompt


@pytest.mark.asyncio
async def test_a_mixed_issue_names_the_source_and_forbids_framing() -> None:
    prompt = await _prompt_for(
        ImplicationKind.CHANGES_PRACTICE,
        ImplicationKind.WORTH_ATTENTION,
        ImplicationKind.NO_CHANGE,
    )
    assert "Only part of this issue changes practice: Fonte 1" in prompt
    assert "attribute it to that source by name" in prompt
    assert "Do not frame the issue as a whole around it" in prompt


@pytest.mark.asyncio
async def test_an_issue_that_changes_nothing_forbids_operational_framing() -> None:
    prompt = await _prompt_for(
        ImplicationKind.WORTH_ATTENTION,
        ImplicationKind.NO_CHANGE,
    )
    assert "operational framing is forbidden" in prompt
    assert "Only part of this issue" not in prompt


@pytest.mark.asyncio
async def test_an_issue_that_wholly_changes_practice_is_not_restricted() -> None:
    prompt = await _prompt_for(
        ImplicationKind.CHANGES_PRACTICE,
        ImplicationKind.CHANGES_PRACTICE,
    )
    assert "Every item in this issue changes practice." in prompt
    assert "forbidden" not in prompt
