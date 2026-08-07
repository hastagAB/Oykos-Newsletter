"""Tests for schema initialisation.

On 2026-08-06 a deploy that added four mapped columns took the site down:
``create_all`` creates missing tables but never adds columns, so the running app
queried a column the database did not have and crash-looped. These tests cover
the three states a real database can be in when the app starts.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from oykos.db.repository import NewsItemRepository
from oykos.db.schema import init_schema
from oykos.db.tables import Base
from oykos.models.news_item import ContentBlock, NewsItem, SourceRef


def _tables(path: Path) -> set[str]:
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    finally:
        con.close()


def _revision(path: Path) -> str:
    con = sqlite3.connect(path)
    try:
        if "alembic_version" not in _tables(path):
            return ""
        row = con.execute("select version_num from alembic_version").fetchone()
        return row[0] if row else ""
    finally:
        con.close()


async def _init(path: Path) -> None:
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await init_schema(conn, url)
    finally:
        await engine.dispose()


async def _create_legacy_with_data(path: Path) -> None:
    """A database built the old way: real tables, no Alembic version."""
    url = f"sqlite+aiosqlite:///{path.as_posix()}"
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            await NewsItemRepository(session).save(
                NewsItem(
                    source=SourceRef(
                        key="sip",
                        name="SIP",
                        source_type="rss",
                        country="IT",
                        reliability_tier=4,
                    ),
                    content=ContentBlock(title="Titolo", canonical_url="https://sip.it/a"),
                ),
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_empty_database_is_created_at_head(tmp_path: Path) -> None:
    db = tmp_path / "empty.db"

    await _init(db)

    assert "news_items" in _tables(db)
    assert _revision(db) != ""


@pytest.mark.asyncio
async def test_legacy_database_is_stamped_not_rebuilt(tmp_path: Path) -> None:
    """A pre-Alembic database already has the tables, so replaying the initial
    migration would fail. It must be stamped instead."""
    db = tmp_path / "legacy.db"
    await _create_legacy_with_data(db)
    assert _revision(db) == ""

    await _init(db)

    assert _revision(db) != ""


@pytest.mark.asyncio
async def test_stamping_never_destroys_data(tmp_path: Path) -> None:
    """The whole point of stamping instead of recreating: subscribers survive."""
    db = tmp_path / "legacy.db"
    await _create_legacy_with_data(db)

    await _init(db)

    con = sqlite3.connect(db)
    try:
        count = con.execute("select count(*) from news_items").fetchone()[0]
    finally:
        con.close()
    assert count == 1


@pytest.mark.asyncio
async def test_init_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "repeat.db"

    await _init(db)
    first = _revision(db)
    await _init(db)

    assert _revision(db) == first


@pytest.mark.asyncio
async def test_new_tables_appear_on_an_existing_database(tmp_path: Path) -> None:
    """Adding a table must not require a wipe."""
    db = tmp_path / "grow.db"
    await _create_legacy_with_data(db)

    await _init(db)

    assert {"events", "event_sources_resolved", "click_events"} <= _tables(db)
