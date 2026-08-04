"""Oykos Newsletter Engine - CLI entry point.

Usage:
    oykos ingest             Daily run (Mon-Fri): ingest, classify, score, alert
    oykos compose            Weekly run: compose the issue and queue it for review
    oykos send               Deliver issues an editor has approved
    oykos run                Ingest then compose, in order
    oykos serve              Web server: subscribers, preferences, archive, review
    oykos check-smtp         Verify the SMTP connection without sending anything
    oykos check-sources      Fetch every source and report which ones work
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

VERSION = "1.1.0"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oykos",
        description="Italian Pediatrics Newsletter Engine for PLS",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Hold the issue for review instead of sending it",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("ingest", help="Daily ingestion, classification and alerts")
    sub.add_parser("compose", help="Weekly composition, queued for editorial review")
    sub.add_parser("send", help="Deliver approved issues")
    sub.add_parser("run", help="Daily ingestion followed by weekly composition")
    sub.add_parser("check-smtp", help="Verify the SMTP connection without sending")
    sub.add_parser("check-sources", help="Fetch every source and report what works")

    serve = sub.add_parser("serve", help="Start the web server")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host")
    serve.add_argument("--port", type=int, default=8000, help="Bind port")
    return parser


def cli() -> None:
    """Entry point for ``python -m oykos`` and the ``oykos`` console script."""
    args = _build_parser().parse_args()

    if args.version:
        print(f"oykos-newsletter {VERSION}")  # noqa: T201
        sys.exit(0)

    if args.command == "serve":
        import uvicorn  # noqa: PLC0415

        uvicorn.run("oykos.web.app:app", host=args.host, port=args.port, reload=False)
        return

    if args.command == "check-smtp":
        from oykos.config import Settings  # noqa: PLC0415
        from oykos.delivery.preflight import check_smtp  # noqa: PLC0415

        result = check_smtp(Settings())  # type: ignore[call-arg]
        print(f"{'OK' if result.ok else 'FAILED'}: {result.summary}")  # noqa: T201
        for hint in result.hints:
            print(f"  - {hint}")  # noqa: T201
        sys.exit(0 if result.ok else 1)

    if args.command == "check-sources":
        from oykos.ingestion.health import check_sources  # noqa: PLC0415

        results = asyncio.run(check_sources())
        working = [r for r in results if r.ok]
        for result in results:
            status = "OK  " if result.ok else "DEAD"
            detail = result.error or f"{result.items} items"
            print(f"{status} {result.key:24} {result.source_type.value:7} {detail}")  # noqa: T201
        print(f"\n{len(working)}/{len(results)} sources returned items.")  # noqa: T201
        sys.exit(0 if working else 1)

    if args.preview:
        os.environ["PREVIEW_MODE"] = "true"

    # Lazy import keeps CLI startup (and --version) fast.
    from oykos.pipeline.runner import (  # noqa: PLC0415
        run_daily,
        run_pipeline,
        run_weekly,
        send_pending,
    )

    if args.command == "ingest":
        asyncio.run(run_daily())
    elif args.command == "compose":
        asyncio.run(run_weekly())
    elif args.command == "send":
        asyncio.run(send_pending())
    else:
        asyncio.run(run_pipeline())


if __name__ == "__main__":
    cli()
