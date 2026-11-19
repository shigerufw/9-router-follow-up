"""One refresh path shared by the CLI, cron/launchd and the local server."""

from __future__ import annotations

import fcntl
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import inventory as inventory_mod
from . import openrouter, render, sources

DEFAULT_OUT = Path("dist") / "models.html"


class Busy(RuntimeError):
    """Another refresh is already writing the report."""


@dataclass
class Report:
    path: Path
    generated: str
    openrouter_source: str
    summary: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def acquire_lock(out: Path):
    """Non-blocking exclusive lock next to the report; released on close/exit."""
    lock_path = Path(out).with_name(Path(out).name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise Busy(f"another refresh holds {lock_path}") from None
    return handle


def generate(
    out: Path | str = DEFAULT_OUT,
    *,
    home: Path | str | None = None,
    cache: Path | str | None = None,
    offline: bool = False,
    force_fetch: bool = False,
    generated: str | None = None,
    product: str = "9router-follow-up",
    lock: bool = True,
) -> Report:
    """Read 9router + OpenRouter, render the page and replace it atomically."""
    out = Path(out)
    handle = acquire_lock(out) if lock else None
    try:
        snapshot = sources.load_local(home or sources.DEFAULT_HOME)
        catalog = openrouter.load(
            cache or openrouter.DEFAULT_CACHE, offline=offline, refresh=force_fetch
        )
        inventory = inventory_mod.build(snapshot, catalog.models)
        if catalog.warning:
            inventory.warnings.insert(0, catalog.warning)

        stamp = generated or timestamp()
        html = render.build_html(
            inventory, product=product, generated=stamp, or_source=catalog.source
        )

        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
        try:
            tmp.write_text(html, encoding="utf-8")
            os.replace(tmp, out)
        finally:
            tmp.unlink(missing_ok=True)

        return Report(
            path=out,
            generated=stamp,
            openrouter_source=catalog.source,
            summary=inventory.summary(),
            warnings=list(inventory.warnings),
        )
    finally:
        if handle is not None:
            handle.close()  # releases the flock; the file itself is reused next time
