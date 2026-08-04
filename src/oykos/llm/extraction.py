"""Evidence snippet extraction - S018.

Before any editorial text is written, 3-8 verbatim passages are pulled from the
source document. Everything downstream (synthesis, verification, citations) is
grounded on these passages, which is what makes source -> claim traceability
possible (blueprint Section 7, non-negotiable principle 1).
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from oykos.llm.client import LLMClient
from oykos.models.news_item import KeyPassage, NewsItem

logger = logging.getLogger(__name__)

MIN_PASSAGES = 3
MAX_PASSAGES = 8
MAX_SOURCE_CHARS = 12000

EXTRACTION_SYSTEM = """You extract verbatim evidence passages from Italian and English
pediatric source documents.

Rules:
- Quote the source EXACTLY. Never paraphrase, translate or summarise a quote.
- Choose passages that carry facts a pediatrician would act on: recommendations,
  dosages, thresholds, dates, obligations, safety signals, surveillance figures.
- Skip navigation text, cookie banners, author lists and boilerplate.
- Return between 3 and 8 passages. If the document supports fewer, return fewer."""


class ExtractedPassage(BaseModel):
    quote: str
    location: str = ""


class ExtractionResponse(BaseModel):
    passages: list[ExtractedPassage] = Field(default_factory=list)


def _verbatim(quote: str, source_text: str) -> bool:
    """Guard against paraphrase: a passage must actually occur in the source."""
    needle = " ".join(quote.split()).lower()
    haystack = " ".join(source_text.split()).lower()
    return bool(needle) and needle in haystack


async def extract_key_passages(item: NewsItem, client: LLMClient) -> list[KeyPassage]:
    """Extract 3-8 grounded evidence snippets from an item's source text."""
    source_text = item.content.raw_text
    if not source_text.strip():
        return []

    prompt = f"""Extract the key evidence passages from this document.

Title: {item.content.title}
Source: {item.source.name} ({item.source.country})
URL: {item.content.canonical_url}

DOCUMENT:
{source_text[:MAX_SOURCE_CHARS]}"""

    try:
        response = await client.complete_structured(
            prompt=prompt,
            response_model=ExtractionResponse,
            system=EXTRACTION_SYSTEM,
        )
    except Exception:
        logger.exception("Evidence extraction failed for %s", item.content.title)
        return []

    passages: list[KeyPassage] = []
    for extracted in response.passages[:MAX_PASSAGES]:
        quote = extracted.quote.strip()
        if not quote:
            continue
        if not _verbatim(quote, source_text):
            logger.warning(
                "Discarding non-verbatim passage for %s: %.60s",
                item.content.title,
                quote,
            )
            continue
        passages.append(
            KeyPassage(
                quote=quote,
                location=extracted.location,
                url=item.content.canonical_url,
            ),
        )

    return passages


async def attach_key_passages(item: NewsItem, client: LLMClient) -> NewsItem:
    """Populate ``item.content.key_passages`` in place and return the item."""
    item.content.key_passages = await extract_key_passages(item, client)
    return item
