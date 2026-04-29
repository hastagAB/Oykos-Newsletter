"""Main weekly pipeline - ties all phases together."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from oykos.alerts.pipeline import process_alerts
from oykos.config import Settings
from oykos.db.repository import NewsItemRepository, NewsletterRepository
from oykos.ingestion.orchestrator import run_daily_ingestion
from oykos.llm.classifier import classify_item
from oykos.llm.client import LLMClient
from oykos.llm.synthesis import synthesize_editorial
from oykos.llm.verification import verify_claims
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.subject import generate_subject_lines
from oykos.newsletter.template import render_html, render_plain_text
from oykos.observability.metrics import compute_quality_report
from oykos.processing.scoring import score_item

logger = logging.getLogger(__name__)


async def run_daily_pipeline(session: AsyncSession, settings: Settings) -> None:
    """Run the daily ingestion + classification + scoring pipeline."""
    logger.info("Starting daily pipeline")

    # 1. Ingest
    items = await run_daily_ingestion(session)
    logger.info("Ingested %d items", len(items))

    # 2. Classify + Score
    client = LLMClient(settings)
    repo = NewsItemRepository(session)

    for item in items:
        classification, subscores = await classify_item(item, client)
        item.classification = classification
        item.scoring.subscores = subscores
        await repo.update_classification(str(item.item_id), classification)

        scoring = score_item(item)
        item.scoring = scoring
        await repo.update_scoring(str(item.item_id), scoring)

    await session.commit()

    # 3. Check for alerts
    await process_alerts(items, settings)

    logger.info("Daily pipeline complete")


async def run_weekly_pipeline(session: AsyncSession, settings: Settings) -> None:
    """Run the weekly newsletter composition pipeline."""
    logger.info("Starting weekly pipeline")
    client = LLMClient(settings)
    repo = NewsItemRepository(session)
    nl_repo = NewsletterRepository(session)

    # 1. Get candidates
    candidates = await repo.get_candidates(min_score=30.0, limit=50)
    logger.info("Found %d candidates", len(candidates))

    # 2. Generate editorial for top candidates
    for item in candidates[:20]:
        if not item.editorial.headline_operational:
            editorial = await synthesize_editorial(item, client)
            editorial = await verify_claims(editorial, item.content.raw_text, client)
            item.editorial = editorial
            await repo.update_editorial(str(item.item_id), editorial)

    await session.commit()

    # 3. Compose newsletter
    week = datetime.utcnow().strftime("%G-W%V")
    newsletter = compose_newsletter(candidates, week, settings.newsletter_title)

    # 4. Subject lines
    subject_a, subject_b = await generate_subject_lines(newsletter, client)
    newsletter.subject_line = subject_a
    newsletter.subject_variant = subject_b

    # 5. Render
    newsletter.html_content = render_html(newsletter, settings.newsletter_title)
    newsletter.text_content = render_plain_text(newsletter, settings.newsletter_title)

    # 6. Persist
    await nl_repo.save(newsletter)
    await session.commit()

    # 7. Quality report
    report = compute_quality_report(candidates, newsletter)
    logger.info("Weekly pipeline complete: %s", week)
