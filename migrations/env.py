"""Alembic environment configuration for async SQLAlchemy."""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add src to path so oykos is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from oykos.db.tables import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url_from_environment() -> None:
    """Read DATABASE_URL, loading .env only when Alembic runs standalone.

    Importing dotenv at module level leaked the developer's .env into the whole
    pytest session once the app started driving migrations in-process, which
    made an unrelated delivery test fail depending on ordering.
    """
    from dotenv import load_dotenv  # noqa: PLC0415

    load_dotenv()
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL)."""
    _url_from_environment()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # noqa: ANN001
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    The app passes an existing synchronous connection through
    ``config.attributes`` so the schema can be brought to head at startup
    without opening a second engine.
    """
    connection = config.attributes.get("connection")
    if connection is not None:
        do_run_migrations(connection)
        return
    _url_from_environment()
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
