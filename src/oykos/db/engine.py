"""Database engine and session management - S005."""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

metadata = MetaData()


class Base(DeclarativeBase):
    metadata = metadata


def get_engine(database_url: str):  # noqa: ANN201
    return create_async_engine(database_url, echo=False)


def get_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = get_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_tables(database_url: str) -> None:
    engine = get_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
