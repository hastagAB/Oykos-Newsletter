"""Repository layer for CRUD operations - S005."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.tables import AlertRow, NewsItemRow, NewsletterRow, ReviewDecisionRow
from oykos.models.news_item import (
    Citation,
    Classification,
    ContentBlock,
    EditorialBlock,
    Gating,
    IssueMetrics,
    KeyPassage,
    NewsItem,
    Newsletter,
    NewsletterSlot,
    ReviewDecision,
    ReviewStatus,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import (
    Confidence,
    DocumentType,
    ExclusionReason,
    Geo,
    IssueStatus,
    Setting,
    TaxonomyTag,
)


def utcnow() -> datetime:
    """Naive UTC timestamp for database comparisons."""
    return datetime.now(UTC).replace(tzinfo=None)


def _naive(value: datetime | None) -> datetime | None:
    """Strip the offset from an aware datetime, converting to UTC first."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class NewsItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, item: NewsItem) -> None:
        row = NewsItemRow(
            item_id=str(item.item_id),
            ingested_at=_naive(item.ingested_at),
            source_key=item.source.key,
            source_name=item.source.name,
            source_country=item.source.country,
            source_reliability=item.source.reliability_tier,
            title=item.content.title,
            canonical_url=item.content.canonical_url,
            published_at=_naive(item.content.published_at),
            document_type=item.content.document_type.value,
            language=item.content.language,
            raw_text=item.content.raw_text,
            geo=item.classification.geo.value,
            taxonomy_tags=[t.value for t in item.classification.taxonomy_tags],
            setting=item.classification.setting.value,
            pls_relevance=item.classification.pls_relevance,
            device_related=item.classification.device_related,
            score_total=item.scoring.score_total,
            subscores=item.scoring.subscores.model_dump(),
            penalties=item.scoring.penalties,
            transferability=item.scoring.transferability,
            hook_question=item.editorial.hook_question,
            headline_operational=item.editorial.headline_operational,
            why_it_matters=item.editorial.why_it_matters,
            what_to_do=item.editorial.what_to_do,
            summary=item.editorial.summary,
            confidence=item.editorial.confidence.value,
            citations=[c.model_dump() for c in item.editorial.citations],
            key_passages=[p.model_dump() for p in item.content.key_passages],
            needs_human_review=item.editorial.review.needs_human_review,
            review_status=item.editorial.review.review_status,
            reviewer_role=item.editorial.review.reviewer_role,
            review_reason=item.editorial.review.review_reason,
            gate_passed=item.gating.passed,
            exclusions=[e.value for e in item.gating.exclusions],
            unsupported_claims=item.editorial.unsupported_claims,
            blocked=item.editorial.blocked,
        )
        self.session.add(row)
        await self.session.flush()

    async def get_by_id(self, item_id: str) -> NewsItem | None:
        stmt = select(NewsItemRow).where(NewsItemRow.item_id == item_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_model(row)

    async def get_by_url(self, url: str) -> NewsItem | None:
        stmt = select(NewsItemRow).where(NewsItemRow.canonical_url == url)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_model(row)

    async def url_exists(self, url: str) -> bool:
        stmt = select(NewsItemRow.item_id).where(NewsItemRow.canonical_url == url)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_recent_titles(self, days: int = 28) -> list[str]:
        cutoff = utcnow() - timedelta(days=days)
        stmt = select(NewsItemRow.title).where(NewsItemRow.ingested_at >= cutoff)
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]

    async def get_unscored(self) -> list[NewsItem]:
        stmt = select(NewsItemRow).where(NewsItemRow.score_total == 0.0)
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    async def get_candidates(self, min_score: float = 0.0, limit: int = 30) -> list[NewsItem]:
        stmt = (
            select(NewsItemRow)
            .where(NewsItemRow.score_total >= min_score)
            .order_by(NewsItemRow.score_total.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    async def get_unsent_candidates(
        self, min_score: float = 30.0, limit: int = 30, max_age_days: int = 7,
    ) -> list[NewsItem]:
        """Get scored items that have never been sent, ingested within max_age_days."""
        cutoff = utcnow() - timedelta(days=max_age_days)
        stmt = (
            select(NewsItemRow)
            .where(
                NewsItemRow.score_total >= min_score,
                NewsItemRow.sent_at.is_(None),
                NewsItemRow.blocked.is_(False),
                NewsItemRow.ingested_at >= cutoff,
            )
            .order_by(NewsItemRow.score_total.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    async def get_backlog(
        self, min_score: float = 30.0, limit: int = 20, max_age_days: int = 28,
    ) -> list[NewsItem]:
        """Get older unsent items as backlog - older than 7 days but within max_age_days."""
        recent_cutoff = utcnow() - timedelta(days=7)
        old_cutoff = utcnow() - timedelta(days=max_age_days)
        stmt = (
            select(NewsItemRow)
            .where(
                NewsItemRow.score_total >= min_score,
                NewsItemRow.sent_at.is_(None),
                NewsItemRow.blocked.is_(False),
                NewsItemRow.ingested_at < recent_cutoff,
                NewsItemRow.ingested_at >= old_cutoff,
            )
            .order_by(NewsItemRow.score_total.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    async def mark_items_sent(self, item_ids: list[str]) -> None:
        """Mark items as sent so they are excluded from future newsletters."""
        if not item_ids:
            return
        stmt = (
            update(NewsItemRow)
            .where(NewsItemRow.item_id.in_(item_ids))
            .values(sent_at=utcnow())
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def update_gating(self, item_id: str, gating: Gating) -> None:
        row = await self._get_row(item_id)
        if row:
            row.gate_passed = gating.passed
            row.exclusions = [e.value for e in gating.exclusions]
            await self.session.flush()

    async def update_key_passages(self, item_id: str, passages: list[KeyPassage]) -> None:
        row = await self._get_row(item_id)
        if row:
            row.key_passages = [p.model_dump() for p in passages]
            await self.session.flush()

    async def _get_row(self, item_id: str) -> NewsItemRow | None:
        stmt = select(NewsItemRow).where(NewsItemRow.item_id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_classification(self, item_id: str, classification: Classification) -> None:
        row = await self._get_row(item_id)
        if row:
            row.geo = classification.geo.value
            row.taxonomy_tags = [t.value for t in classification.taxonomy_tags]
            row.setting = classification.setting.value
            row.pls_relevance = classification.pls_relevance
            row.device_related = classification.device_related
            await self.session.flush()

    async def update_scoring(self, item_id: str, scoring: ScoringBlock) -> None:
        row = await self._get_row(item_id)
        if row:
            row.score_total = scoring.score_total
            row.subscores = scoring.subscores.model_dump()
            row.penalties = scoring.penalties
            row.transferability = scoring.transferability
            await self.session.flush()

    async def update_editorial(self, item_id: str, editorial: EditorialBlock) -> None:
        row = await self._get_row(item_id)
        if row:
            row.hook_question = editorial.hook_question
            row.headline_operational = editorial.headline_operational
            row.why_it_matters = editorial.why_it_matters
            row.what_to_do = editorial.what_to_do
            row.summary = editorial.summary
            row.confidence = editorial.confidence.value
            row.citations = [c.model_dump() for c in editorial.citations]
            row.needs_human_review = editorial.review.needs_human_review
            row.review_status = editorial.review.review_status
            row.reviewer_role = editorial.review.reviewer_role
            row.review_reason = editorial.review.review_reason
            row.unsupported_claims = editorial.unsupported_claims
            row.blocked = editorial.blocked
            await self.session.flush()

    def _row_to_model(self, row: NewsItemRow) -> NewsItem:
        from uuid import UUID

        return NewsItem(
            item_id=UUID(row.item_id),
            ingested_at=row.ingested_at,
            source=SourceRef(
                key=row.source_key,
                name=row.source_name,
                source_type="rss",
                country=row.source_country,
                reliability_tier=row.source_reliability,
            ),
            content=ContentBlock(
                title=row.title,
                canonical_url=row.canonical_url,
                published_at=row.published_at,
                document_type=DocumentType(row.document_type),
                language=row.language,
                raw_text=row.raw_text,
                key_passages=[KeyPassage(**p) for p in (row.key_passages or [])],
            ),
            classification=Classification(
                geo=Geo(row.geo),
                taxonomy_tags=[TaxonomyTag(t) for t in (row.taxonomy_tags or [])],
                setting=Setting(row.setting),
                pls_relevance=row.pls_relevance,
                device_related=row.device_related,
            ),
            scoring=ScoringBlock(
                score_total=row.score_total,
                subscores=Subscores(**row.subscores) if row.subscores else Subscores(),
                penalties=row.penalties if row.penalties else [],
            ),
            editorial=EditorialBlock(
                hook_question=row.hook_question,
                headline_operational=row.headline_operational,
                why_it_matters=row.why_it_matters,
                what_to_do=row.what_to_do if row.what_to_do else [],
                summary=row.summary,
                confidence=Confidence(row.confidence) if row.confidence else Confidence.LOW,
                citations=[Citation(**c) for c in (row.citations or [])],
                unsupported_claims=list(row.unsupported_claims or []),
                blocked=bool(row.blocked),
                review=ReviewStatus(
                    needs_human_review=row.needs_human_review,
                    review_status=row.review_status,
                    reviewer_role=row.reviewer_role,
                    review_reason=row.review_reason or "",
                ),
            ),
            gating=Gating(
                passed=bool(row.gate_passed),
                exclusions=[ExclusionReason(e) for e in (row.exclusions or [])],
            ),
        )


class NewsletterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, newsletter: Newsletter) -> None:
        row = NewsletterRow(
            issue_id=str(newsletter.issue_id),
            week=newsletter.week,
            created_at=_naive(newsletter.created_at),
            subject_line=newsletter.subject_line,
            preheader=newsletter.preheader,
            tldr=newsletter.tldr,
            reading_time_minutes=newsletter.reading_time_minutes,
            html_content=newsletter.html_content,
            text_content=newsletter.text_content,
            public_url=newsletter.public_url,
            status=newsletter.status.value,
            slots=[s.model_dump(mode="json") for s in newsletter.slots],
            metrics=newsletter.metrics.model_dump(),
        )
        self.session.add(row)
        await self.session.flush()

    async def get_by_week(self, week: str) -> Newsletter | None:
        stmt = (
            select(NewsletterRow)
            .where(NewsletterRow.week == week)
            .order_by(NewsletterRow.created_at.desc())
        )
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        return None if row is None else self._row_to_model(row)

    async def get_by_id(self, issue_id: str) -> Newsletter | None:
        row = await self._get_row(issue_id)
        return None if row is None else self._row_to_model(row)

    async def list_by_status(self, status: IssueStatus, limit: int = 20) -> list[Newsletter]:
        stmt = (
            select(NewsletterRow)
            .where(NewsletterRow.status == status.value)
            .order_by(NewsletterRow.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    async def update_status(self, issue_id: str, status: IssueStatus) -> None:
        row = await self._get_row(issue_id)
        if row is None:
            return
        row.status = status.value
        if status is IssueStatus.IN_REVIEW and row.review_started_at is None:
            row.review_started_at = utcnow()
        elif status is IssueStatus.APPROVED:
            row.approved_at = utcnow()
        elif status is IssueStatus.SENT:
            row.sent_at = utcnow()
        await self.session.flush()

    async def mark_approved(self, issue_id: str, approved_by: str) -> None:
        row = await self._get_row(issue_id)
        if row is None:
            return
        row.status = IssueStatus.APPROVED.value
        row.approved_at = utcnow()
        row.approved_by = approved_by
        await self.session.flush()

    async def update_slots(self, issue_id: str, slots: list[NewsletterSlot]) -> None:
        """Persist edited slots, e.g. after an editor rewrites a headline."""
        row = await self._get_row(issue_id)
        if row is None:
            return
        row.slots = [s.model_dump(mode="json") for s in slots]
        await self.session.flush()

    async def update_rendered(self, issue_id: str, html: str, text: str) -> None:
        row = await self._get_row(issue_id)
        if row is None:
            return
        row.html_content = html
        row.text_content = text
        await self.session.flush()

    async def update_public_url(self, issue_id: str, public_url: str) -> None:
        row = await self._get_row(issue_id)
        if row is None:
            return
        row.public_url = public_url
        await self.session.flush()

    async def _get_row(self, issue_id: str) -> NewsletterRow | None:
        stmt = select(NewsletterRow).where(NewsletterRow.issue_id == issue_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _row_to_model(self, row: NewsletterRow) -> Newsletter:
        from uuid import UUID

        return Newsletter(
            issue_id=UUID(row.issue_id),
            week=row.week,
            created_at=row.created_at,
            subject_line=row.subject_line,
            preheader=row.preheader or "",
            tldr=list(row.tldr or []),
            reading_time_minutes=row.reading_time_minutes or 0,
            html_content=row.html_content,
            text_content=row.text_content,
            public_url=row.public_url or "",
            status=IssueStatus(row.status),
            slots=[NewsletterSlot(**s) for s in (row.slots or [])],
            metrics=IssueMetrics(**row.metrics) if row.metrics else IssueMetrics(),
        )


class ReviewDecisionRepository:
    """Audit trail of editorial decisions - the corrections-rate KPI reads this."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, decision: ReviewDecision) -> None:
        self.session.add(
            ReviewDecisionRow(
                decision_id=str(decision.decision_id),
                item_id=str(decision.item_id),
                issue_id=str(decision.issue_id),
                reviewer_role=decision.reviewer_role,
                status=decision.status,
                edits=decision.edits,
                notes=decision.notes,
                decided_at=_naive(decision.decided_at),
            ),
        )
        await self.session.flush()

    async def list_for_issue(self, issue_id: str) -> list[ReviewDecision]:
        stmt = (
            select(ReviewDecisionRow)
            .where(ReviewDecisionRow.issue_id == issue_id)
            .order_by(ReviewDecisionRow.decided_at.asc())
        )
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    async def latest_by_item(self, issue_id: str) -> dict[str, ReviewDecision]:
        """Most recent decision per item, which is what the UI renders."""
        latest: dict[str, ReviewDecision] = {}
        for decision in await self.list_for_issue(issue_id):
            latest[str(decision.item_id)] = decision
        return latest

    async def list_recent(self, days: int = 90) -> list[ReviewDecision]:
        cutoff = utcnow() - timedelta(days=days)
        stmt = select(ReviewDecisionRow).where(ReviewDecisionRow.decided_at >= cutoff)
        result = await self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.scalars().all()]

    def _row_to_model(self, row: ReviewDecisionRow) -> ReviewDecision:
        from uuid import UUID

        return ReviewDecision(
            decision_id=UUID(row.decision_id),
            item_id=UUID(row.item_id),
            issue_id=UUID(row.issue_id),
            reviewer_role=row.reviewer_role,
            status=row.status,
            edits=row.edits,
            notes=row.notes,
            decided_at=row.decided_at,
        )


class AlertRepository:
    """Ledger for trigger alerts, enforcing the blueprint's monthly cap."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_last_30_days(self) -> int:
        cutoff = utcnow() - timedelta(days=30)
        stmt = (
            select(func.count())
            .select_from(AlertRow)
            .where(AlertRow.sent_at >= cutoff)
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def already_alerted(self, item_id: str) -> bool:
        stmt = select(AlertRow.alert_id).where(AlertRow.item_id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def record(
        self,
        item_id: str,
        category: str,
        level: str,
        subject: str,
        recipients: int,
    ) -> None:
        self.session.add(
            AlertRow(
                item_id=item_id,
                category=category,
                level=level,
                subject=subject,
                recipients=recipients,
                sent_at=utcnow(),
            ),
        )
        await self.session.flush()
