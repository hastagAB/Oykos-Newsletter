"""Database engine and session management - S005."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from oykos.db.tables import Base

__all__ = ["Base", "create_tables", "get_engine", "get_session_factory"]


def get_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, echo=False)


def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = get_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(database_url: str) -> None:
    """Create every table declared on the ORM metadata."""
    engine = get_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()
