"""Schema initialisation.

``Base.metadata.create_all`` creates missing tables but never adds columns to a
table that already exists. Adding a mapped column and deploying therefore left
the running app querying a column the database did not have, which crash-looped
it and took the site down on 2026-08-06.

So the schema is brought up by Alembic. A database that predates Alembic is
stamped at the current head first, because its tables already exist and the
initial migration would fail against them.
"""
from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncConnection

from oykos.db.tables import Base

logger = logging.getLogger(__name__)

# A table that exists in every version of the schema, used to tell "empty
# database" apart from "database that predates Alembic".
SENTINEL_TABLE = "news_items"


def _alembic_config(database_url: str) -> Config:
    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _upgrade(connection, config: Config) -> None:  # type: ignore[no-untyped-def]
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


def _stamp(connection, config: Config) -> None:  # type: ignore[no-untyped-def]
    config.attributes["connection"] = connection
    command.stamp(config, "head")


def _plan(connection) -> tuple[bool, bool]:  # type: ignore[no-untyped-def]
    """Return (database_is_empty, already_stamped)."""
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    context = MigrationContext.configure(connection)
    return SENTINEL_TABLE not in tables, context.get_current_revision() is not None


async def init_schema(connection: AsyncConnection, database_url: str) -> None:
    """Bring the schema to head, whatever state it starts in."""
    config = _alembic_config(database_url)
    try:
        is_empty, stamped = await connection.run_sync(_plan)
    except Exception:
        logger.exception("Could not inspect the database - falling back to create_all")
        await connection.run_sync(Base.metadata.create_all)
        return

    try:
        if is_empty:
            await connection.run_sync(_upgrade, config)
            logger.info("Schema created at head")
            return

        if not stamped:
            # Pre-Alembic database: its tables exist, so replaying the initial
            # migration would fail. Record where it is, then migrate forward.
            await connection.run_sync(_stamp, config)
            logger.info("Existing database stamped at head")
            return

        head = ScriptDirectory.from_config(config).get_current_head()
        await connection.run_sync(_upgrade, config)
        logger.info("Schema migrated to %s", head)
    except Exception:
        # A failed migration must not stop the app from serving; it must be
        # loud instead. create_all still creates genuinely missing tables.
        logger.exception("Migration failed - the schema may be behind the code")
        await connection.run_sync(Base.metadata.create_all)
