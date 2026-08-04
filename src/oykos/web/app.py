"""FastAPI application: public subscriber surface plus the editorial review UI.

State (settings, session factory) lives on ``app.state`` so routers can depend on
it without module-level globals.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from oykos.config import Settings
from oykos.db.tables import Base
from oykos.observability.logging import setup_logging
from oykos.web.public import router as public_router
from oykos.web.review import router as review_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = Settings()  # type: ignore[call-arg]
    setup_logging(settings.log_level)

    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app.state.settings = settings
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    if not settings.review_enabled:
        logger.warning(
            "REVIEW_TOKEN is not set - the editorial review interface is disabled",
        )

    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Oykos Newsletter",
    version="1.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.include_router(public_router)
app.include_router(review_router)
