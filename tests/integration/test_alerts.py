"""Trigger alerts: which hard events fire, and the monthly cap.

Over-notification is how this product loses its audience, so both halves matter:
only four categories may fire, and never more than the configured budget.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oykos.alerts.pipeline import process_alerts
from oykos.alerts.triggers import AlertCategory, AlertLevel, classify_alert
from oykos.config import Settings
from oykos.db.repository import AlertRepository
from oykos.db.tables import Base
from oykos.models.news_item import (
    Classification,
    ContentBlock,
    EditorialBlock,
    NewsItem,
    ScoringBlock,
    SourceRef,
    Subscores,
)
from oykos.models.taxonomy import DocumentType, Geo, TaxonomyTag


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        openai_api_key="sk-test",
        smtp_username="a@b.it",
        smtp_password="pw",
        recipient_emails="pls@example.it",
        max_alerts_per_month=2,
        _env_file=None,
    )  # type: ignore[call-arg]


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    async def fake_send(**kwargs) -> bool:
        captured.append(kwargs)
        return True

    monkeypatch.setattr("oykos.alerts.pipeline.send_newsletter", fake_send)
    return captured


def _item(
    *,
    title: str = "Richiamo lotti",
    source_key: str = "aifa_safety",
    tags: list[TaxonomyTag] | None = None,
    doc_type: DocumentType = DocumentType.SAFETY_COMMUNICATION,
    urgency: int = 5,
    clinical_impact: int = 2,
    operational_impact: int = 2,
    reliability: int = 5,
    device_related: bool = False,
) -> NewsItem:
    return NewsItem(
        source=SourceRef(
            key=source_key,
            name="Fonte",
            source_type="scrape",
            country="IT",
            reliability_tier=reliability,
        ),
        content=ContentBlock(
            title=title,
            canonical_url=f"https://www.aifa.gov.it/{title}",
            document_type=doc_type,
        ),
        classification=Classification(
            geo=Geo.IT,
            taxonomy_tags=tags if tags is not None else [TaxonomyTag.DRUG_SAFETY],
            device_related=device_related,
        ),
        scoring=ScoringBlock(
            subscores=Subscores(
                urgency=urgency,
                clinical_impact=clinical_impact,
                operational_impact=operational_impact,
                source_trust=reliability,
            ),
        ),
        editorial=EditorialBlock(headline_operational="Verificare i lotti"),
    )


# ── Which events qualify ──────────────────────────────────

def test_the_four_hard_categories_fire() -> None:
    assert classify_alert(_item()) is AlertCategory.DRUG_SAFETY

    assert classify_alert(
        _item(source_key="min_salute_fsn", tags=[TaxonomyTag.DEVICE_SAFETY], device_related=True),
    ) is AlertCategory.DEVICE_SAFETY

    assert classify_alert(
        _item(
            source_key="respivirnet",
            tags=[TaxonomyTag.SURVEILLANCE],
            doc_type=DocumentType.SURVEILLANCE_REPORT,
            clinical_impact=4,
        ),
    ) is AlertCategory.EPIDEMIC_SURVEILLANCE

    assert classify_alert(
        _item(
            source_key="sisac_acn",
            tags=[TaxonomyTag.ACN_AGREEMENTS],
            doc_type=DocumentType.LEGAL_UPDATE,
            operational_impact=5,
        ),
    ) is AlertCategory.ACN_CHANGE


@pytest.mark.parametrize(
    ("label", "item"),
    [
        ("new guideline", _item(doc_type=DocumentType.GUIDELINE, tags=[], clinical_impact=5)),
        ("drug shortage", _item(tags=[TaxonomyTag.DRUG_SHORTAGE])),
        ("vaccination news", _item(tags=[TaxonomyTag.VACCINATIONS], doc_type=DocumentType.NEWS)),
        ("routine news", _item(tags=[TaxonomyTag.RESPIRATORY], doc_type=DocumentType.NEWS, urgency=2)),
        ("weak source", _item(reliability=2)),
    ],
)
def test_digest_material_never_triggers_an_alert(label: str, item: NewsItem) -> None:
    assert classify_alert(item) is None, f"{label} should stay in the weekly digest"


# ── The cap ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_alert_is_sent_and_recorded(session, settings, sent) -> None:
    triggered = await process_alerts([_item()], settings, session)

    assert [level for _, level in triggered] == [AlertLevel.CRITICAL]
    assert len(sent) == 1
    assert await AlertRepository(session).count_last_30_days() == 1


@pytest.mark.asyncio
async def test_monthly_cap_suppresses_the_rest(session, settings, sent) -> None:
    items = [_item(title=f"Richiamo {i}") for i in range(5)]

    triggered = await process_alerts(items, settings, session)

    assert len(triggered) == settings.max_alerts_per_month


@pytest.mark.asyncio
async def test_budget_carries_across_runs(session, settings, sent) -> None:
    await process_alerts([_item(title="Primo")], settings, session)
    await process_alerts([_item(title="Secondo")], settings, session)

    assert await process_alerts([_item(title="Terzo")], settings, session) == []


@pytest.mark.asyncio
async def test_the_same_item_never_alerts_twice(session, settings, sent) -> None:
    item = _item()
    await process_alerts([item], settings, session)

    assert await process_alerts([item], settings, session) == []
