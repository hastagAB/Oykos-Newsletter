"""Repository layer for CRUD operations - S005."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from oykos.db.tables import NewsItemRow, NewsletterRow, ReviewDecisionRow
from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    Newsletter,
    ReviewDecision,
    ReviewStatus,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import Confidence, DocumentType, Geo, IssueStatus, Setting


class NewsItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, item: NewsItem) -> None:
        row = NewsItemRow(
            item_id=str(item.item_id),
            ingested_at=item.ingested_at,
            source_key=item.source.key,
            source_name=item.source.name,
            source_country=item.source.country,
            source_reliability=item.source.reliability_tier,
            title=item.content.title,
            canonical_url=item.content.canonical_url,
            published_at=item.content.published_at,
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
        cutoff = datetime.utcnow() - timedelta(days=days)
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
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        stmt = (
            select(NewsItemRow)
            .where(
                NewsItemRow.score_total >= min_score,
                NewsItemRow.sent_at.is_(None),
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
        """Get older unsent items as backlog - items older than 7 days but within max_age_days."""
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        old_cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        stmt = (
            select(NewsItemRow)
            .where(
                NewsItemRow.score_total >= min_score,
                NewsItemRow.sent_at.is_(None),
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
        now = datetime.utcnow()
        stmt = (
            update(NewsItemRow)
            .where(NewsItemRow.item_id.in_(item_ids))
            .values(sent_at=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def update_classification(self, item_id: str, classification: Classification) -> None:
        stmt = select(NewsItemRow).where(NewsItemRow.item_id == item_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.geo = classification.geo.value
            row.taxonomy_tags = [t.value for t in classification.taxonomy_tags]
            row.setting = classification.setting.value
            row.pls_relevance = classification.pls_relevance
            row.device_related = classification.device_related
            await self.session.flush()

    async def update_scoring(self, item_id: str, scoring: ScoringBlock) -> None:
        stmt = select(NewsItemRow).where(NewsItemRow.item_id == item_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.score_total = scoring.score_total
            row.subscores = scoring.subscores.model_dump()
            row.penalties = scoring.penalties
            row.transferability = scoring.transferability
            await self.session.flush()

    async def update_editorial(self, item_id: str, editorial: EditorialBlock) -> None:
        stmt = select(NewsItemRow).where(NewsItemRow.item_id == item_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.headline_operational = editorial.headline_operational
            row.why_it_matters = editorial.why_it_matters
            row.what_to_do = editorial.what_to_do
            row.summary = editorial.summary
            row.confidence = editorial.confidence.value
            row.citations = [c.model_dump() for c in editorial.citations]
            row.needs_human_review = editorial.review.needs_human_review
            row.review_status = editorial.review.review_status
            row.reviewer_role = editorial.review.reviewer_role
            await self.session.flush()

    def _row_to_model(self, row: NewsItemRow) -> NewsItem:
        from uuid import UUID

        from oykos.models.news_item import Citation, KeyPassage

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
                taxonomy_tags=[t for t in row.taxonomy_tags] if row.taxonomy_tags else [],
                setting=Setting(row.setting),
                pls_relevance=row.pls_relevance,
                device_related=row.device_related,
            ),
            scoring=ScoringBlock(
                score_total=row.score_total,
                subscores=Subscores(**row.subscores) if row.subscores else Subscores(),
                penalties=row.penalties if row.penalties else [],
                transferability=row.transferability,
            ),
            editorial=EditorialBlock(
                headline_operational=row.headline_operational,
                why_it_matters=row.why_it_matters,
                what_to_do=row.what_to_do if row.what_to_do else [],
                summary=row.summary,
                confidence=Confidence(row.confidence) if row.confidence else Confidence.LOW,
                citations=[Citation(**c) for c in (row.citations or [])],
                review=ReviewStatus(
                    needs_human_review=row.needs_human_review,
                    review_status=row.review_status,
                    reviewer_role=row.reviewer_role,
                ),
            ),
        )


class NewsletterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, newsletter: Newsletter) -> None:
        row = NewsletterRow(
            issue_id=str(newsletter.issue_id),
            week=newsletter.week,
            created_at=newsletter.created_at,
            subject_line=newsletter.subject_line,
            subject_variant=newsletter.subject_variant,
            html_content=newsletter.html_content,
            text_content=newsletter.text_content,
            status=newsletter.status.value,
            slots=[s.model_dump(mode="json") for s in newsletter.slots],
            metrics=newsletter.metrics.model_dump(),
        )
        self.session.add(row)
        await self.session.flush()

    async def get_by_week(self, week: str) -> Newsletter | None:
        stmt = select(NewsletterRow).where(NewsletterRow.week == week)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_model(row)

    async def update_status(self, issue_id: str, status: IssueStatus) -> None:
        stmt = select(NewsletterRow).where(NewsletterRow.issue_id == issue_id)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.status = status.value
            await self.session.flush()

    def _row_to_model(self, row: NewsletterRow) -> Newsletter:
        from uuid import UUID

        from oykos.models.news_item import IssueMetrics, NewsletterSlot

        return Newsletter(
            issue_id=UUID(row.issue_id),
            week=row.week,
            created_at=row.created_at,
            subject_line=row.subject_line,
            subject_variant=row.subject_variant,
            html_content=row.html_content,
            text_content=row.text_content,
            status=IssueStatus(row.status),
            slots=[NewsletterSlot(**s) for s in (row.slots or [])],
            metrics=IssueMetrics(**row.metrics) if row.metrics else IssueMetrics(),
        )
