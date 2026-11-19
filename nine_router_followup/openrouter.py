"""OpenRouter model catalogue: fetch once, cache on disk, fail soft.

The dashboard must work with no network: a stale cache is always preferred over
an empty table.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API_URL = "https://openrouter.ai/api/v1/models"
DEFAULT_CACHE = Path.home() / ".cache" / "9router-followup" / "openrouter-models.json"
TTL_S = 24 * 3600


@dataclass
class Catalog:
    models: dict[str, dict] = field(default_factory=dict)
    source: str = "none"  # network | cache | none
    fetched_at: float | None = None
    warning: str | None = None

    def __bool__(self) -> bool:
        return bool(self.models)


def http_get_json(url: str = API_URL, timeout: float = 25.0) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "9router-followup"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = json.loads(response.read())
    models = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(models, list):
        raise ValueError("unexpected OpenRouter payload: no model list")
    return [m for m in models if isinstance(m, dict) and isinstance(m.get("id"), str)]


def _index(models: list[dict]) -> dict[str, dict]:
    return {m["id"]: m for m in models}


def read_cache(path: Path) -> tuple[dict[str, dict], float | None]:
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}, None
    if not isinstance(payload, dict):
        return {}, None
    models = payload.get("models")
    fetched_at = payload.get("fetched_at")
    if not isinstance(models, dict):
        return {}, None
    return {k: v for k, v in models.items() if isinstance(v, dict)}, (
        float(fetched_at) if isinstance(fetched_at, (int, float)) else None
    )


def write_cache(path: Path, models: dict[str, dict], fetched_at: float) -> None:
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps({"fetched_at": fetched_at, "models": models}))
        tmp.replace(path)
    except OSError:
        pass  # a read-only cache dir must not break the report


def load(
    cache_path: Path | str = DEFAULT_CACHE,
    *,
    offline: bool = False,
    refresh: bool = False,
    ttl: float = TTL_S,
    fetcher=None,
    now: float | None = None,
) -> Catalog:
    """Return the model catalogue, preferring a fresh fetch when allowed."""
    cache_path = Path(cache_path).expanduser()
    now = time.time() if now is None else now
    cached, fetched_at = read_cache(cache_path)
    fresh = fetched_at is not None and (now - fetched_at) < ttl
    fetcher = fetcher or http_get_json

    if not offline and (refresh or not cached or not fresh):
        try:
            models = _index(fetcher())
            if models:
                write_cache(cache_path, models, now)
                return Catalog(models=models, source="network", fetched_at=now)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            warning = f"OpenRouter fetch failed ({e}); using cached models" if cached else (
                f"OpenRouter fetch failed ({e}); no cached models"
            )
            if cached:
                return Catalog(models=cached, source="cache", fetched_at=fetched_at, warning=warning)
            return Catalog(warning=warning)
        except Exception as e:  # noqa: BLE001 - never fail the report on enrichment
            warning = f"OpenRouter fetch failed ({e}); using cached models" if cached else (
                f"OpenRouter fetch failed ({e}); no cached models"
            )
            if cached:
                return Catalog(models=cached, source="cache", fetched_at=fetched_at, warning=warning)
            return Catalog(warning=warning)

    if cached:
        return Catalog(models=cached, source="cache", fetched_at=fetched_at)
    return Catalog(warning="no OpenRouter models cached and fetch disabled (--offline?)")
