"""Run the full newsletter pipeline.

Thin wrapper - delegates to oykos.pipeline.runner.
Usage: python scripts/run_pipeline.py
"""
from __future__ import annotations

import asyncio

from oykos.pipeline.runner import run_pipeline

if __name__ == "__main__":
    asyncio.run(run_pipeline())

