"""Command line entry point: ``python3 -m nine_router_followup dashboard``."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import inventory as inventory_mod
from . import openrouter, render, sources

DEFAULT_OUT = Path("dist") / "models.html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m nine_router_followup",
        description="Read-only dashboards for a local 9router install.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    dash = sub.add_parser("dashboard", help="write the model inventory dashboard")
    dash.add_argument("--out", default=str(DEFAULT_OUT), help="output HTML path")
    dash.add_argument("--home", default=str(sources.DEFAULT_HOME), help="9router home directory")
    dash.add_argument("--cache", default=str(openrouter.DEFAULT_CACHE), help="OpenRouter cache file")
    dash.add_argument("--offline", action="store_true", help="never fetch OpenRouter models")
    dash.add_argument("--refresh", action="store_true", help="force a fetch even if the cache is fresh")
    dash.add_argument("--generated", default=None, help="fixed timestamp (ISO) for reproducible output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "dashboard":
        return 2

    snapshot = sources.load_local(Path(args.home).expanduser())
    catalog = openrouter.load(
        Path(args.cache).expanduser(),
        offline=args.offline,
        refresh=args.refresh,
    )
    inventory = inventory_mod.build(snapshot, catalog.models)
    if catalog.warning:
        inventory.warnings.insert(0, catalog.warning)

    generated = args.generated or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = render.build_html(
        inventory, generated=generated, or_source=catalog.source
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    summary = inventory.summary()
    print(
        f"wrote {out} — {summary['models']} models, "
        f"{summary['models_in_use']} in use, {summary['requests']} requests, "
        f"OpenRouter: {catalog.source}"
    )
    for warning in inventory.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
