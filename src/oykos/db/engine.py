"""Database engine and session management - S005."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from oykos.db.schema import init_schema
from oykos.db.tables import Base

__all__ = ["Base", "create_tables", "get_engine", "get_session_factory"]


def get_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = get_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(database_url: str) -> None:
    """Bring the schema to the current migration head."""
    engine = get_engine(database_url)
    try:
        async with engine.begin() as conn:
            await init_schema(conn, database_url)
    finally:
        await engine.dispose()
