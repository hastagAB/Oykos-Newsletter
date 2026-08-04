"""Shared pytest configuration.

The suite must never read the developer's real ``.env``. ``monkeypatch.delenv``
only clears the process environment; pydantic-settings would still fall back to
the file, so a value present locally but absent in CI silently changes the
result of a test. Disabling the env file for the whole session removes that
whole class of failure.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from oykos.config import Settings


@pytest.fixture(autouse=True, scope="session")
def _ignore_dotenv() -> Iterator[None]:
    original = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    try:
        yield
    finally:
        Settings.model_config["env_file"] = original
