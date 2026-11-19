"""Command line entry point: dashboard, serve."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import openrouter, refresh, serve as serve_mod, sources

DEFAULT_PORT = 4780


def _add_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", default=str(refresh.DEFAULT_OUT), help="output HTML path")
    parser.add_argument("--home", default=str(sources.DEFAULT_HOME), help="9router home directory")
    parser.add_argument("--cache", default=str(openrouter.DEFAULT_CACHE), help="OpenRouter cache file")
    parser.add_argument("--offline", action="store_true", help="never fetch OpenRouter models")
    parser.add_argument(
        "--refresh",
        action="store_true",
        dest="force_fetch",
        help="force an OpenRouter fetch even if the cache is fresh",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m nine_router_followup",
        description="Read-only dashboards for a local 9router install.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    dash = sub.add_parser("dashboard", help="write the model inventory dashboard")
    _add_source_args(dash)
    dash.add_argument("--generated", default=None, help="fixed timestamp (ISO) for reproducible output")
    dash.add_argument(
        "--skip-if-busy",
        action="store_true",
        help="exit 0 when another refresh holds the lock (cron/launchd friendly)",
    )

    srv = sub.add_parser("serve", help="serve the dashboard locally, with a working Refresh button")
    _add_source_args(srv)
    srv.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port (default {DEFAULT_PORT})")
    srv.add_argument("--verbose", action="store_true", help="log every request")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "serve":
        return serve_mod.serve(
            port=args.port,
            out=Path(args.out),
            home=args.home,
            cache=args.cache,
            offline=args.offline,
            force_fetch=args.force_fetch,
            verbose=args.verbose,
        )

    if args.command != "dashboard":
        return 2

    try:
        report = refresh.generate(
            Path(args.out),
            home=args.home,
            cache=args.cache,
            offline=args.offline,
            force_fetch=args.force_fetch,
            generated=args.generated,
        )
    except refresh.Busy as e:
        if args.skip_if_busy:
            print(f"skipped: {e}")
            return 0
        print(f"error: {e} (or pass --skip-if-busy)", file=sys.stderr)
        return 3

    summary = report.summary
    print(
        f"wrote {report.path} — {summary['models']} models, "
        f"{summary['models_in_use']} in use, {summary['requests']} requests, "
        f"OpenRouter: {report.openrouter_source}"
    )
    for warning in report.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
