"""Oykos Newsletter Engine - CLI entry point.

Usage:
    python -m oykos             Run the full daily pipeline
    python -m oykos --preview   Run pipeline in preview mode (no send)
    python -m oykos serve       Start the web server (subscribers, archive, feedback)
"""
from __future__ import annotations

import argparse
import asyncio
import sys


def cli() -> None:
    """Entry point for ``python -m oykos`` and ``oykos`` console script."""
    parser = argparse.ArgumentParser(
        prog="oykos",
        description="Italian Pediatrics Newsletter Engine for PLS",
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version and exit",
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Run pipeline in preview mode (save newsletter without sending)",
    )
    sub = parser.add_subparsers(dest="command")
    serve_parser = sub.add_parser("serve", help="Start the web server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port")

    args = parser.parse_args()

    if args.version:
        print("oykos-newsletter 1.0.0")
        sys.exit(0)

    if args.command == "serve":
        import uvicorn  # noqa: PLC0415
        uvicorn.run("oykos.web.app:app", host=args.host, port=args.port, reload=False)
        return

    # Lazy import to keep CLI startup fast
    from oykos.pipeline.runner import run_pipeline  # noqa: PLC0415

    if args.preview:
        import os  # noqa: PLC0415
        os.environ["PREVIEW_MODE"] = "true"

    asyncio.run(run_pipeline())


if __name__ == "__main__":
    cli()
