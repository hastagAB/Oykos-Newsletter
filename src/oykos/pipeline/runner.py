"""Full newsletter pipeline - ingest, classify, score, compose, send.

Daily flow:
  1. Ingest RSS feeds and persist to DB (dedup via URL + title similarity)
  2. Classify + score new items with Azure OpenAI
  3. Gather unsent candidates; pull from backlog if needed
  4. Synthesize editorial for top candidates
  5. Compose newsletter (70/30 IT/foreign ratio)
  6. Generate A/B subject lines
  7. Render HTML + plain text
  8. Preview gate (optional) - pause for human review
  9. Send via Gmail SMTP (per-subscriber with unsubscribe headers)
  10. Healthcheck ping
  11. Mark sent items in DB so they are never repeated
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.config import Settings
from oykos.db.repository import NewsItemRepository, NewsletterRepository
from oykos.db.subscribers import SubscriberRepository
from oykos.db.tables import Base
from oykos.delivery.email_sender import send_newsletter
from oykos.ingestion.normalizer import clean_html, normalize_url
from oykos.ingestion.rss import fetch_rss
from oykos.llm.classifier import classify_item
from oykos.llm.client import LLMClient
from oykos.llm.synthesis import synthesize_editorial
from oykos.llm.verification import verify_claims
from oykos.models.news_item import NewsItem
from oykos.models.source import get_source_registry
from oykos.models.taxonomy import Geo, IssueStatus, SourceType, Tier
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.subject import generate_subject_lines
from oykos.newsletter.template import render_html, render_plain_text
from oykos.processing.scoring import score_item

logger = logging.getLogger("oykos.runner")

MIN_NEWSLETTER_ITEMS = 5


async def _ingest_and_persist(
    session: AsyncSession, repo: NewsItemRepository,
) -> list[NewsItem]:
    """Phase 1: Fetch RSS, dedup against DB, persist new items."""
    registry = get_source_registry()
    rss_sources = [s for s in registry.values() if s.source_type == SourceType.RSS and s.enabled]
    logger.info("  %d RSS sources to fetch", len(rss_sources))

    saved: list[NewsItem] = []
    for source in rss_sources:
        try:
            items = await fetch_rss(source)
            for item in items:
                item.content.canonical_url = normalize_url(item.content.canonical_url)
                if item.content.raw_text:
                    item.content.raw_text = clean_html(item.content.raw_text)
                if source.tier == Tier.TIER_1_ITALY:
                    item.classification.geo = Geo.IT
                elif source.tier == Tier.TIER_2_EUROPE:
                    item.classification.geo = Geo.EU
                else:
                    item.classification.geo = Geo.GLOBAL

                if await repo.url_exists(item.content.canonical_url):
                    continue

                await repo.save(item)
                saved.append(item)

            if items:
                logger.info("  [OK] %s: %d fetched, %d new", source.name, len(items),
                            sum(1 for i in saved if i.source.key == source.key))
        except Exception:
            logger.warning("  [SKIP] %s: fetch failed", source.name, exc_info=True)

    await session.commit()
    return saved


async def _classify_and_score(
    items: list[NewsItem], client: LLMClient, repo: NewsItemRepository, session: AsyncSession,
) -> list[NewsItem]:
    """Phase 2: Classify + score items, persist updates."""
    scored: list[NewsItem] = []
    for i, item in enumerate(items[:40], 1):
        try:
            logger.info("  [%d/%d] Classifying: %.60s...", i, min(len(items), 40), item.content.title)
            classification, subscores = await classify_item(item, client)
            item.classification = classification
            item.scoring.subscores = subscores
            scoring = score_item(item)
            item.scoring = scoring
            await repo.update_classification(str(item.item_id), classification)
            await repo.update_scoring(str(item.item_id), scoring)
            scored.append(item)
            logger.info("         Score: %.1f", scoring.score_total)
        except Exception:
            logger.warning("  [SKIP] Classification failed: %s", item.content.title[:60])
    await session.commit()
    return scored


async def _synthesize_editorial(
    items: list[NewsItem], client: LLMClient, repo: NewsItemRepository, session: AsyncSession,
) -> None:
    """Phase 4: Generate editorial for candidates missing it."""
    need_editorial = [i for i in items if not i.editorial.headline_operational][:15]
    for i, item in enumerate(need_editorial, 1):
        try:
            logger.info("  [%d/%d] Synthesizing: %.60s...", i, len(need_editorial), item.content.title)
            editorial = await synthesize_editorial(item, client)
            editorial = await verify_claims(editorial, item.content.raw_text, client)
            item.editorial = editorial
            await repo.update_editorial(str(item.item_id), editorial)
            logger.info("         Headline: %s", editorial.headline_operational[:80])
        except Exception:
            logger.warning("  [SKIP] Synthesis failed: %s", item.content.title[:60])
    await session.commit()


async def run_pipeline() -> None:
    """Execute the full daily newsletter pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        stream=sys.stdout,
    )

    settings = Settings()  # type: ignore[call-arg]
    week = datetime.utcnow().strftime("%G-W%V")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    logger.info("=== Oykos Newsletter Pipeline - %s (%s) ===", week, today)

    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        repo = NewsItemRepository(session)
        nl_repo = NewsletterRepository(session)
        client = LLMClient(settings)

        # Phase 1: Ingest
        logger.info("Phase 1: Ingesting RSS feeds (with dedup)...")
        new_items = await _ingest_and_persist(session, repo)
        logger.info("Persisted %d new articles", len(new_items))

        # Phase 2: Classify + Score
        logger.info("Phase 2: Classifying and scoring new items...")
        unscored = await repo.get_unscored()
        logger.info("  %d unscored items in DB", len(unscored))
        if unscored:
            await _classify_and_score(unscored, client, repo, session)

        # Phase 3: Gather candidates + backlog
        logger.info("Phase 3: Gathering unsent candidates...")
        candidates = await repo.get_unsent_candidates(min_score=30.0, limit=30)
        logger.info("  %d fresh unsent candidates (last 7 days)", len(candidates))

        if len(candidates) < MIN_NEWSLETTER_ITEMS:
            logger.info("  Not enough fresh items (%d < %d). Pulling from backlog...",
                        len(candidates), MIN_NEWSLETTER_ITEMS)
            backlog = await repo.get_backlog(min_score=20.0, limit=20)
            logger.info("  %d backlog items available (7-28 days old)", len(backlog))
            seen_ids = {str(c.item_id) for c in candidates}
            for item in backlog:
                if str(item.item_id) not in seen_ids:
                    candidates.append(item)
                    seen_ids.add(str(item.item_id))
            logger.info("  Total candidates after backlog: %d", len(candidates))

        if not candidates:
            logger.error("No candidates available. Cannot build newsletter. Exiting.")
            await engine.dispose()
            return

        # Phase 4: Synthesize editorial
        logger.info("Phase 4: Generating editorial content...")
        await _synthesize_editorial(candidates, client, repo, session)

        # Phase 5: Compose newsletter
        logger.info("Phase 5: Composing newsletter...")
        newsletter = compose_newsletter(candidates, week, settings.newsletter_title)
        logger.info("  Slots: %d | IT: %d | Foreign: %d",
                    len(newsletter.slots),
                    newsletter.metrics.italy_count,
                    newsletter.metrics.foreign_count)

        if not newsletter.slots:
            logger.error("Newsletter has 0 slots. Cannot send. Exiting.")
            await engine.dispose()
            return

        # Phase 6: Render
        logger.info("Phase 6: Rendering HTML + plain text...")
        newsletter.html_content = render_html(newsletter, settings.newsletter_title)
        newsletter.text_content = render_plain_text(newsletter, settings.newsletter_title)

        # Phase 6b: Generate A/B subject lines
        logger.info("  Generating A/B subject lines...")
        subject_a, subject_b = await generate_subject_lines(newsletter, client)
        newsletter.subject_line = subject_a
        newsletter.subject_variant = subject_b
        logger.info("  Subject A: %s", subject_a)
        logger.info("  Subject B: %s", subject_b)
        logger.info("  HTML: %d bytes | Text: %d bytes",
                    len(newsletter.html_content), len(newsletter.text_content))

        # Phase 7: Preview gate
        if settings.preview_mode:
            newsletter.status = IssueStatus.IN_REVIEW
            await nl_repo.save(newsletter)
            await session.commit()
            logger.info("=== PREVIEW MODE: Newsletter saved as draft (issue_id=%s) ===",
                        newsletter.issue_id)
            logger.info("Review at: %s/api/newsletters/%s", settings.base_url, newsletter.week)
            await engine.dispose()
            return

        # Phase 8: Send (subscriber-based with A/B split + unsubscribe headers)
        sub_repo = SubscriberRepository(session)
        active_subs = await sub_repo.get_active_subscribers()
        # Fall back to RECIPIENT_EMAILS if no subscribers in DB yet
        if active_subs:
            ab_split = max(1, len(active_subs) * settings.ab_test_percent // 100)
            group_b = active_subs[:ab_split]
            group_a = active_subs[ab_split:]
            logger.info("Phase 8: Sending to %d subscribers (A=%d, B=%d)...",
                        len(active_subs), len(group_a), len(group_b))

            # Send subject B to test group
            for sub in group_b:
                unsub_url = f"{settings.base_url}/unsubscribe/{sub.unsubscribe_token}"
                await send_newsletter(
                    settings=settings,
                    to_emails=[sub.email],
                    subject=subject_b,
                    html_content=newsletter.html_content,
                    text_content=newsletter.text_content,
                    list_unsubscribe_url=unsub_url,
                )

            # Send subject A to main group
            for sub in group_a:
                unsub_url = f"{settings.base_url}/unsubscribe/{sub.unsubscribe_token}"
                await send_newsletter(
                    settings=settings,
                    to_emails=[sub.email],
                    subject=subject_a,
                    html_content=newsletter.html_content,
                    text_content=newsletter.text_content,
                    list_unsubscribe_url=unsub_url,
                )
            ok = True
        else:
            # Legacy fallback: send to RECIPIENT_EMAILS
            recipients = settings.recipient_list
            if not recipients:
                logger.error("No subscribers and no RECIPIENT_EMAILS configured.")
                await engine.dispose()
                return
            logger.info("Phase 8: Sending to %d legacy recipients...", len(recipients))
            ok = await send_newsletter(
                settings=settings,
                to_emails=recipients,
                subject=newsletter.subject_line,
                html_content=newsletter.html_content,
                text_content=newsletter.text_content,
            )

        if ok:
            sent_ids = [str(slot.item_id) for slot in newsletter.slots]
            await repo.mark_items_sent(sent_ids)
            newsletter.status = IssueStatus.SENT
            await nl_repo.save(newsletter)
            await session.commit()
            logger.info("=== Newsletter sent! %d items marked as sent ===", len(sent_ids))
        else:
            logger.error("=== Email delivery FAILED - items NOT marked as sent ===")

        # Phase 9: Healthcheck ping
        if settings.healthcheck_ping_url:
            try:
                async with httpx.AsyncClient(timeout=10) as hc:
                    resp = await hc.get(settings.healthcheck_ping_url)
                    logger.info("Healthcheck ping: %d", resp.status_code)
            except Exception:
                logger.warning("Healthcheck ping failed", exc_info=True)

    await engine.dispose()
