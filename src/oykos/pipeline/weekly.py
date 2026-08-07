"""Weekly pipeline - the composer run that actually ships an issue.

Order matters and follows the blueprint end-to-end workflow (Section 7):
candidates -> evidence snippets -> editorial synthesis -> verification ->
Decision Cards -> composer with constraints -> subject/preheader -> render ->
risk-based human review gate -> delivery.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from oykos.config import Settings
from oykos.db.repository import (
    NewsItemRepository,
    NewsletterRepository,
    ReviewDecisionRepository,
)
from oykos.db.subscribers import SubscriberRepository
from oykos.delivery.email_sender import OutboundMessage, send_bulk, send_newsletter
from oykos.delivery.tracking import tracked_url
from oykos.delivery.wordpress import publish_issue
from oykos.llm.client import LLMClient
from oykos.llm.extraction import attach_key_passages
from oykos.llm.synthesis import synthesize_editorial
from oykos.llm.verification import cross_source_support, verify_claims
from oykos.models.news_item import NewsItem, Newsletter
from oykos.models.taxonomy import Confidence, IssueStatus
from oykos.newsletter.composer import compose_newsletter
from oykos.newsletter.subject import generate_subject_line
from oykos.newsletter.template import CTA_TITLE, render_html, render_plain_text
from oykos.observability.metrics import compute_quality_report
from oykos.processing.gates import filter_candidates
from oykos.processing.ranker import rank_and_select
from oykos.processing.recency import filter_to_week

logger = logging.getLogger(__name__)

MIN_NEWSLETTER_ITEMS = 5
CANDIDATE_MIN_SCORE = 30.0
BACKLOG_MIN_SCORE = 20.0
# A couple of spares, so a verification block does not shorten the issue.
EDITORIAL_HEADROOM = 3


def current_week() -> str:
    return datetime.now(UTC).strftime("%G-W%V")


async def gather_candidates(repo: NewsItemRepository) -> list[NewsItem]:
    """Fresh unsent candidates, topped up from the 7-28 day backlog if sparse."""
    candidates = await repo.get_unsent_candidates(min_score=CANDIDATE_MIN_SCORE, limit=40)
    logger.info("%d fresh unsent candidates (last 7 days)", len(candidates))

    if len(candidates) >= MIN_NEWSLETTER_ITEMS:
        return candidates

    logger.info("Only %d fresh candidates - pulling backlog", len(candidates))
    seen = {c.item_id for c in candidates}
    for item in await repo.get_backlog(min_score=BACKLOG_MIN_SCORE, limit=20):
        if item.item_id not in seen:
            candidates.append(item)
            seen.add(item.item_id)

    logger.info("%d candidates after backlog top-up", len(candidates))
    return candidates


async def build_editorial(
    candidates: list[NewsItem],
    client: LLMClient,
    repo: NewsItemRepository,
) -> None:
    """Extract evidence, synthesise and verify, in place.

    Only called with items that already survived gating and ranking, so no LLM
    budget is spent writing copy for items that will not ship.
    """
    pending = [c for c in candidates if not c.editorial.headline_operational]
    corroborating = {c.source.key for c in candidates}

    for index, item in enumerate(pending, start=1):
        logger.info("[%d/%d] Editorial: %.70s", index, len(pending), item.content.title)
        try:
            await attach_key_passages(item, client)
            await repo.update_key_passages(str(item.item_id), item.content.key_passages)

            editorial = await synthesize_editorial(item, client)
            item.editorial = await verify_claims(editorial, item, client)

            # Cross-source corroboration (AIFA <-> EMA, ISS <-> Ministry). A second
            # institutional source covering the same ground restores confidence that
            # single-source verification had to hold back.
            if (
                not item.editorial.blocked
                and item.editorial.confidence is Confidence.MEDIUM
                and cross_source_support(item, corroborating - {item.source.key})
            ):
                item.editorial.confidence = Confidence.HIGH

            await repo.update_editorial(str(item.item_id), item.editorial)

            if item.editorial.blocked:
                logger.warning("Item blocked by verification: %.70s", item.content.title)
        except Exception:
            logger.exception("Editorial generation failed: %.70s", item.content.title)


async def deliver(
    newsletter: Newsletter,
    settings: Settings,
    session: AsyncSession,
) -> bool:
    """Send the issue to every confirmed subscriber."""
    subscriber_repo = SubscriberRepository(session)
    subscribers = await subscriber_repo.get_active_subscribers()

    if not subscribers:
        recipients = settings.recipient_list
        if not recipients:
            logger.error("No confirmed subscribers and no RECIPIENT_EMAILS configured")
            return False
        logger.info("Sending to %d legacy recipients", len(recipients))
        return await send_newsletter(
            settings=settings,
            to_emails=recipients,
            subject=newsletter.subject_line,
            html_content=newsletter.html_content,
            text_content=newsletter.text_content,
        )

    logger.info("Sending to %d subscribers", len(subscribers))
    if settings.click_tracking and not settings.tracking_enabled:
        logger.warning("CLICK_TRACKING is on but TRACKING_SECRET is empty - not tracking")

    # One rendered message per subscriber, so each gets their own unsubscribe
    # and preferences link. Sent over a shared, throttled connection.
    messages: list[OutboundMessage] = []
    for subscriber in subscribers:
        unsubscribe_url = (
            f"{settings.base_url.rstrip('/')}/unsubscribe/{subscriber.unsubscribe_token}"
        )
        preferences_url = settings.preferences_url_for(subscriber.unsubscribe_token)
        cta_url = _tracked(
            settings, newsletter, subscriber.unsubscribe_token, "cta", settings.cta_url,
        )
        subject = _variant(
            newsletter, subscriber.ab_group, "subject", newsletter.subject_line,
        )
        cta_title = _variant(newsletter, subscriber.ab_group, "cta", "")
        html = render_html(
            newsletter,
            settings.newsletter_title,
            unsubscribe_url=unsubscribe_url,
            preferences_url=preferences_url,
            archive_url=settings.archive_url,
            cta_url=cta_url,
            logo_url=settings.logo_url,
            preheader=_variant(
                newsletter, subscriber.ab_group, "preheader", newsletter.preheader,
            ),
            cta_title=cta_title,
        )
        messages.append(
            OutboundMessage(
                to_email=subscriber.email,
                subject=subject,
                html_content=_track_source_links(
                    settings, newsletter, subscriber.unsubscribe_token, html,
                ),
                text_content=render_plain_text(
                    newsletter,
                    settings.newsletter_title,
                    unsubscribe_url=unsubscribe_url,
                    preferences_url=preferences_url,
                    cta_url=cta_url,
                    cta_title=cta_title,
                ),
                list_unsubscribe_url=unsubscribe_url,
            ),
        )

    delivered = await send_bulk(settings, messages)
    logger.info("Delivered %d/%d", delivered, len(subscribers))
    return delivered > 0


def _variant(newsletter: Newsletter, ab_group: str, element: str, default: str) -> str:
    """The B text when this issue varies ``element`` and the reader is in B."""
    if ab_group != "B" or newsletter.ab_element != element or not newsletter.ab_variant_b:
        return default
    return newsletter.ab_variant_b


def _tracked(
    settings: Settings,
    newsletter: Newsletter,
    subscriber_token: str,
    kind: str,
    url: str,
) -> str:
    if not settings.tracking_enabled or not url:
        return url
    return tracked_url(
        base_url=settings.base_url,
        issue_id=str(newsletter.issue_id),
        subscriber_token=subscriber_token,
        kind=kind,
        url=url,
        secret=settings.tracking_secret.get_secret_value(),
    )


def _track_source_links(
    settings: Settings,
    newsletter: Newsletter,
    subscriber_token: str,
    html: str,
) -> str:
    """Rewrite outbound source links to go through the redirect endpoint.

    Only external destinations are rewritten: unsubscribe, preferences and
    archive links must keep working even if tracking is later switched off.
    """
    if not settings.tracking_enabled:
        return html

    own = settings.base_url.rstrip("/")

    def replace(match: re.Match[str]) -> str:
        url = match.group(1)
        if url.startswith(own) or not url.startswith("http"):
            return match.group(0)
        return f'href="{_tracked(settings, newsletter, subscriber_token, "source", url)}"'

    return re.sub(r'href="(https?://[^"]+)"', replace, html)


async def deliver_and_finalize(
    newsletter: Newsletter,
    settings: Settings,
    session: AsyncSession,
) -> bool:
    """Deliver the issue, then publish it and mark everything sent.

    Shared by the scheduled run and the "send now" button in the review UI, so
    both paths finalise identically.
    """
    newsletter_repo = NewsletterRepository(session)

    # Publish first so the email can carry a working "Leggi online" link.
    public_url = await publish_issue(settings, newsletter)
    if public_url:
        newsletter.public_url = public_url
        await newsletter_repo.update_public_url(str(newsletter.issue_id), public_url)

    if not await deliver(newsletter, settings, session):
        return False

    await NewsItemRepository(session).mark_items_sent(
        [str(slot.item_id) for slot in newsletter.slots],
    )
    # Click rates are meaningless without the denominator.
    await newsletter_repo.update_sent_count(
        str(newsletter.issue_id),
        await SubscriberRepository(session).count_active(),
    )
    await newsletter_repo.update_status(str(newsletter.issue_id), IssueStatus.SENT)
    newsletter.status = IssueStatus.SENT
    logger.info("Issue %s sent, %d items marked", newsletter.week, len(newsletter.slots))
    return True


async def run_weekly_pipeline(session: AsyncSession, settings: Settings) -> Newsletter | None:
    """Compose, review-gate and deliver the weekly issue."""
    week = current_week()
    logger.info("=== Weekly pipeline: %s ===", week)

    client = LLMClient(settings)
    repo = NewsItemRepository(session)
    newsletter_repo = NewsletterRepository(session)

    candidates = await gather_candidates(repo)
    if not candidates:
        logger.error("No candidates available - cannot build an issue")
        return None

    # Recency is not a tie-breaker, it is a precondition: an item outside this
    # week cannot ship, so it must never occupy a shortlist slot or cost a
    # synthesis call. Filter before ranking, not after.
    in_week = filter_to_week(filter_candidates(candidates), week)
    logger.info("%d of %d candidates were published in %s", len(in_week), len(candidates), week)
    if not in_week:
        logger.error("Nothing was published in %s - no issue to build", week)
        return None

    # Gate and rank BEFORE writing any copy: synthesis is the expensive call, so
    # it only runs on items that have already earned a slot.
    shortlist = [
        item
        for item, _ in rank_and_select(
            in_week,
            max_total=settings.max_newsletter_items + EDITORIAL_HEADROOM,
            max_italy=settings.max_italy_slots + EDITORIAL_HEADROOM,
            max_foreign=settings.max_foreign_slots + EDITORIAL_HEADROOM,
        )
    ]
    logger.info("%d candidates shortlisted for editorial", len(shortlist))

    await build_editorial(shortlist, client, repo)
    await session.commit()

    newsletter = compose_newsletter(
        shortlist,
        week,
        settings.newsletter_title,
        max_total=settings.max_newsletter_items,
        max_italy=settings.max_italy_slots,
        max_foreign=settings.max_foreign_slots,
    )
    if not newsletter.slots:
        logger.error("Newsletter has 0 slots after gating - nothing to send")
        return None

    lines = await generate_subject_line(newsletter, client, CTA_TITLE)
    newsletter.subject_line = lines.subject
    newsletter.preheader = lines.preheader
    # Vary exactly one element, so any difference in clicks is attributable.
    variant_b = lines.variant_for(settings.ab_element)
    if variant_b:
        newsletter.ab_element = settings.ab_element
        newsletter.ab_variant_b = variant_b
    elif settings.ab_element != "none":
        logger.warning(
            "AB_ELEMENT=%s but no B text was generated - sending one version to everyone",
            settings.ab_element,
        )

    newsletter.html_content = render_html(
        newsletter,
        settings.newsletter_title,
        unsubscribe_url=f"{settings.base_url.rstrip('/')}/unsubscribe/preview",
        preferences_url=settings.preferences_url,
        archive_url=settings.archive_url,
        cta_url=settings.cta_url,
        logo_url=settings.logo_url,
    )
    newsletter.text_content = render_plain_text(
        newsletter,
        settings.newsletter_title,
        preferences_url=settings.preferences_url,
        cta_url=settings.cta_url,
    )

    report = compute_quality_report(shortlist, newsletter)
    for issue in report.issues:
        logger.warning("Quality issue: %s", issue)

    # Risk-based human review gate: high-risk items must be signed off first.
    awaiting = [
        slot for slot in newsletter.slots
        if slot.editorial.review.needs_human_review
        and slot.editorial.review.review_status != "approved"
    ]
    if settings.preview_mode or awaiting:
        newsletter.status = IssueStatus.IN_REVIEW
        await newsletter_repo.save(newsletter)
        await session.commit()
        logger.info(
            "Issue %s held for review: %d item(s) need sign-off. Review at %s/review/%s",
            week, len(awaiting), settings.base_url.rstrip("/"), week,
        )
        return newsletter

    newsletter.status = IssueStatus.APPROVED
    await newsletter_repo.save(newsletter)
    await session.commit()

    if not await deliver_and_finalize(newsletter, settings, session):
        logger.error("Delivery failed - items NOT marked as sent")
    await session.commit()
    return newsletter


async def send_approved_issues(session: AsyncSession, settings: Settings) -> list[Newsletter]:
    """Deliver every issue an editor has approved but that has not gone out yet.

    Also honours ``AUTO_SEND_AFTER_HOURS``: when set, an issue that has been
    waiting in review longer than the SLA ships with only the items that either
    were approved or never needed review. Items still awaiting sign-off are
    dropped rather than sent unreviewed. When the setting is 0 (the default) an
    issue waits for a human indefinitely.
    """
    newsletter_repo = NewsletterRepository(session)
    decisions_repo = ReviewDecisionRepository(session)
    sent: list[Newsletter] = []

    for newsletter in await newsletter_repo.list_by_status(IssueStatus.APPROVED):
        if await deliver_and_finalize(newsletter, settings, session):
            sent.append(newsletter)

    if settings.auto_send_after_hours > 0:
        deadline = datetime.now(UTC) - timedelta(hours=settings.auto_send_after_hours)
        for newsletter in await newsletter_repo.list_by_status(IssueStatus.IN_REVIEW):
            created = newsletter.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created > deadline:
                continue

            decided = await decisions_repo.latest_by_item(str(newsletter.issue_id))
            newsletter.slots = [
                slot for slot in newsletter.slots
                if not slot.editorial.review.needs_human_review
                or str(slot.item_id) in decided
            ]
            if len(newsletter.slots) < MIN_NEWSLETTER_ITEMS:
                logger.warning(
                    "Issue %s passed the review SLA but only %d items are cleared - holding",
                    newsletter.week, len(newsletter.slots),
                )
                continue

            for position, slot in enumerate(newsletter.slots, start=1):
                slot.position = position
            await newsletter_repo.update_slots(str(newsletter.issue_id), newsletter.slots)
            logger.warning(
                "Issue %s auto-sent after the %dh review SLA with %d cleared items",
                newsletter.week, settings.auto_send_after_hours, len(newsletter.slots),
            )
            if await deliver_and_finalize(newsletter, settings, session):
                sent.append(newsletter)

    await session.commit()
    return sent
