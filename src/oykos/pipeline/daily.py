"""Daily pipeline (Mon-Fri) - ingest, classify, score, gate, alert.

The daily run never sends the newsletter. Its job is to keep the candidate pool
fresh and to fire the rare trigger alerts. Composition and delivery happen once
a week (see :mod:`oykos.pipeline.weekly`).
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from oykos.alerts.pipeline import process_alerts
from oykos.config import Settings
from oykos.db.repository import NewsItemRepository
from oykos.ingestion.orchestrator import run_daily_ingestion
from oykos.llm.classifier import classify_item
from oykos.llm.client import LLMClient
from oykos.models.news_item import NewsItem
from oykos.processing.gates import evaluate_gates
from oykos.processing.scoring import detect_editorial_penalties, score_item

logger = logging.getLogger(__name__)

MAX_CLASSIFY_PER_RUN = 60
# Classification failures are usually systemic (no credit, bad key, provider
# outage), not per-item. Give up rather than burn the queue against a dead API.
MAX_CONSECUTIVE_FAILURES = 5


class ClassificationUnavailableError(RuntimeError):
    """Raised when the LLM fails repeatedly, so the run is aborted loudly."""


async def classify_and_score(
    items: list[NewsItem],
    client: LLMClient,
    repo: NewsItemRepository,
    limit: int = MAX_CLASSIFY_PER_RUN,
) -> list[NewsItem]:
    """Classify, score and gate a batch of items, persisting each result."""
    processed: list[NewsItem] = []
    batch = items[:limit]
    consecutive_failures = 0

    for index, item in enumerate(batch, start=1):
        logger.info("[%d/%d] Classifying: %.70s", index, len(batch), item.content.title)
        try:
            classification, subscores = await classify_item(item, client)
        except Exception:
            logger.exception("Classification failed: %.70s", item.content.title)
            consecutive_failures += 1
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                msg = (
                    f"Aborting: {consecutive_failures} consecutive classification "
                    f"failures. The LLM API is unreachable, out of credit or "
                    f"misconfigured. {len(processed)} item(s) were scored first."
                )
                raise ClassificationUnavailableError(msg) from None
            continue

        consecutive_failures = 0
        item.classification = classification
        item.scoring.subscores = subscores
        # Audience-dependent penalties can only be judged now that the item has
        # a setting and subscores.
        item.scoring.penalties = list(
            dict.fromkeys([*item.scoring.penalties, *detect_editorial_penalties(item)]),
        )
        item.scoring = score_item(item)
        item.gating = evaluate_gates(item)

        await repo.update_classification(str(item.item_id), classification)
        await repo.update_scoring(str(item.item_id), item.scoring)
        await repo.update_gating(str(item.item_id), item.gating)

        processed.append(item)
        logger.info(
            "    score=%.1f gate=%s",
            item.scoring.score_total,
            "pass" if item.gating.passed else "fail",
        )

    return processed


async def run_daily_pipeline(session: AsyncSession, settings: Settings) -> list[NewsItem]:
    """Run daily ingestion, classification, scoring and alert evaluation."""
    logger.info("=== Daily pipeline: ingest, classify, score, gate, alert ===")
    repo = NewsItemRepository(session)
    client = LLMClient(settings)

    ingested = await run_daily_ingestion(session)
    logger.info("Ingested %d new items", len(ingested))

    unscored = await repo.get_unscored()
    logger.info("%d unscored items awaiting classification", len(unscored))
    processed = await classify_and_score(unscored, client, repo)
    await session.commit()

    triggered = await process_alerts(processed, settings, session)
    logger.info("Daily pipeline complete: %d scored, %d alerts", len(processed), len(triggered))
    return processed
