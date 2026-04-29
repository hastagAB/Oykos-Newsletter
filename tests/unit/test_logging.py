"""Tests for structured logging setup - S036."""
from __future__ import annotations

import logging

from oykos.observability.logging import setup_logging


def test_setup_logging_configures_root() -> None:
    setup_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) >= 1


def test_setup_logging_info_level() -> None:
    setup_logging("INFO")
    root = logging.getLogger()
    assert root.level == logging.INFO


def test_setup_logging_suppresses_noisy() -> None:
    setup_logging("INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
