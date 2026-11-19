"""Merge the local 9router snapshot with the OpenRouter catalogue."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .sources import Snapshot, normalize_provider

PER_MILLION = 1_000_000

# "model:free", "model-free", "model-preview" … are variants of one model.
VARIANT_RE = re.compile(r"[:\-](free|batch|extended|thinking|online|beta|alpha|preview)$")
# "…-30b", "…-30b-a3b", "…-e4b", "…-a22b" endings are size/quant tags.
SIZE_RE = re.compile(r"-(?:\d+(?:\.\d+)?[bm](?:-a[\d.]+b)?|e\d+b|a[\d.]+b)$")


@dataclass
class ModelRow:
    provider: str
    model: str
    kind: str = "llm"
    enabled: bool = True
    requests: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    errors: int = 0
    first_seen: str = ""
    last_seen: str = ""
    in_combos: tuple[str, ...] = ()
    # from the 9router catalogue
    context_window: int | None = None
    max_output: int | None = None
    vision: bool | None = None
    # from OpenRouter
    or_id: str | None = None
    or_match: str = ""
    or_name: str | None = None
    or_context: int | None = None
    or_max_output: int | None = None
    prompt_price: float | None = None  # USD per 1M prompt tokens
    completion_price: float | None = None
    modalities: str = ""

    @property
    def in_use(self) -> bool:
        return self.requests > 0

    @property
    def context(self) -> int | None:
        return self.or_context or self.context_window

    @property
    def max_completion(self) -> int | None:
        return self.or_max_output or self.max_output


@dataclass
class Inventory:
    rows: list[ModelRow] = field(default_factory=list)
    providers: list[dict] = field(default_factory=list)
    combos: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def in_use(self) -> list[ModelRow]:
        return [r for r in self.rows if r.in_use]

    @property
    def unmatched(self) -> list[ModelRow]:
        return [r for r in self.rows if r.or_id is None]

    def summary(self) -> dict:
        used = self.in_use
        stamped = [r.last_seen for r in used if r.last_seen]
        return {
            "providers": len(self.providers),
            "connected": sum(1 for p in self.providers if p["active_connections"]),
            "models": len(self.rows),
            "models_in_use": len(used),
            "models_enabled": sum(1 for r in self.rows if r.enabled),
            "combos": len(self.combos),
            "requests": sum(r.requests for r in self.rows),
            "prompt_tokens": sum(r.prompt_tokens for r in self.rows),
            "completion_tokens": sum(r.completion_tokens for r in self.rows),
            "cost": round(sum(r.cost for r in self.rows), 6),
            "errors": sum(r.errors for r in self.rows),
            "matched": len(self.rows) - len(self.unmatched),
            "unmatched": len(self.unmatched),
            "first_seen": min(stamped) if stamped else "",
            "last_seen": max(stamped) if stamped else "",
        }


def _price(value) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price < 0:  # OpenRouter uses -1 for "not applicable"
        return None
    return price * PER_MILLION


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _tail(model_id: str) -> str:
    return model_id.rsplit("/", 1)[-1]


def _strip_variant(model_id: str) -> str:
    return VARIANT_RE.sub("", model_id)


def _strip_sizes(model_id: str) -> str:
    previous = None
    while previous != model_id:
        previous = model_id
        model_id = SIZE_RE.sub("", model_id)
    return model_id


def _pick(hits: list[str], index: dict[str, dict]) -> str | None:
    """Collapse ``id`` / ``id:free`` duplicates; refuse genuinely ambiguous sets."""
    bases: dict[str, list[str]] = {}
    for mid in hits:
        bases.setdefault(_strip_variant(mid), []).append(mid)
    if len(bases) != 1:
        return None
    canonical, members = next(iter(bases.items()))
    return canonical if canonical in index else min(members, key=len)


def match_openrouter(provider: str, model: str, index: dict[str, dict]) -> tuple[str | None, str]:
    """Return (OpenRouter id, match kind) or (None, reason).

    Kinds: exact | provider | variant | tail | fuzzy | ambiguous | no match.
    Only unambiguous matches are accepted, so a wrong price is never shown as
    if it were the model's own.
    """
    if model in index:
        return model, "exact"

    provider = normalize_provider(provider)
    for candidate in (f"{provider}/{model}", f"{provider}/{model}:free"):
        if candidate in index:
            return candidate, "provider"

    target = _strip_variant(_tail(model))

    # same tail, different organisation prefix (meta/ vs meta-llama/) or variant
    hits = [mid for mid in index if _strip_variant(_tail(mid)) == target]
    picked = _pick(hits, index)
    if picked:
        return picked, "variant" if target != model else "tail"
    if len(hits) > 1:
        return None, "ambiguous"

    # 9router keeps size/quant tags that OpenRouter drops (-30b-a3b vs -lightning)
    key = _strip_sizes(target)
    if key != target:
        hits = [mid for mid in index if _strip_sizes(_strip_variant(_tail(mid))) == key]
        picked = _pick(hits, index)
        if picked:
            return picked, "fuzzy"
        if len(hits) > 1:
            return None, "ambiguous"

    return None, "no match"


def _apply_openrouter(row: ModelRow, or_models: dict[str, dict]) -> None:
    or_id, kind = match_openrouter(row.provider, row.model, or_models)
    if or_id is None:
        return
    model = or_models[or_id]
    architecture = model.get("architecture") or {}
    top_provider = model.get("top_provider") or {}
    pricing = model.get("pricing") or {}

    row.or_id = or_id
    row.or_match = kind
    row.or_name = str(model.get("name") or or_id)
    row.or_context = _as_int(model.get("context_length")) or _as_int(
        top_provider.get("context_length")
    )
    row.or_max_output = _as_int(top_provider.get("max_completion_tokens"))
    row.prompt_price = _price(pricing.get("prompt"))
    row.completion_price = _price(pricing.get("completion"))
    row.modalities = str(architecture.get("modality") or "")
    inputs = architecture.get("input_modalities") or []
    if "image" in inputs:
        row.vision = True


def _merge_row(rows: dict, provider: str, model: str, kind: str = "llm") -> ModelRow:
    key = (normalize_provider(provider), model)
    row = rows.get(key)
    if row is None:
        row = ModelRow(provider=normalize_provider(provider), model=model, kind=kind)
        rows[key] = row
    return row


def _split_combo_member(member: str) -> tuple[str, str]:
    provider, _, model = member.partition("/")
    if not model:
        return "", member
    return provider, model


def build(snapshot: Snapshot, or_models: dict[str, dict]) -> Inventory:
    index = or_models if isinstance(or_models, dict) else {}
    rows: dict[tuple[str, str], ModelRow] = {}
    providers_catalog = (snapshot.catalog or {}).get("providers") or {}
    flags = (snapshot.catalog or {}).get("models") or {}

    # 1. what we actually used
    for usage in snapshot.usage:
        row = _merge_row(rows, usage.provider, usage.model)
        row.requests += usage.requests
        row.prompt_tokens += usage.prompt_tokens
        row.completion_tokens += usage.completion_tokens
        row.cost += usage.cost
        row.errors += usage.errors
        row.first_seen = min(filter(None, (row.first_seen, usage.first_seen)), default="")
        row.last_seen = max(row.last_seen, usage.last_seen)

    # 2. custom models we enabled by hand
    for alias, entries in snapshot.custom_models.items():
        for model, kind in entries:
            _merge_row(rows, alias, model, kind)

    # 3. catalogue models of every provider we know about
    known = {normalize_provider(p) for p in snapshot.custom_models}
    known |= {normalize_provider(p) for p in snapshot.disabled_models}
    known |= {c.provider for c in snapshot.connections}
    known |= {u.provider for u in snapshot.usage}
    for provider in sorted(known):
        variants = {provider, provider.replace("opencode", "oc")}
        for variant in variants:
            for model, meta in (providers_catalog.get(variant) or {}).items():
                row = _merge_row(rows, provider, model)
                meta = meta if isinstance(meta, dict) else {}
                row.context_window = row.context_window or _as_int(meta.get("contextWindow"))
                row.max_output = row.max_output or _as_int(meta.get("maxOutput"))

    # 4. explicit disables (they may not be in the catalogue at all)
    for alias, models in snapshot.disabled_models.items():
        for model in models:
            _merge_row(rows, alias, model).enabled = False

    # 5. combos
    combos = []
    for combo in snapshot.combos:
        members = []
        for raw in combo.models:
            provider, model = _split_combo_member(raw)
            key = (normalize_provider(provider), model)
            row = rows.get(key)
            if row is not None:
                row.in_combos = tuple(sorted({*row.in_combos, combo.name}))
            members.append(
                {
                    "raw": raw,
                    "provider": normalize_provider(provider),
                    "model": model,
                    "available": bool(row and row.enabled),
                    "in_use": bool(row and row.in_use),
                }
            )
        combos.append({"name": combo.name, "kind": combo.kind, "members": members})

    # 6. OpenRouter enrichment + vision flag from the 9router catalogue
    for (provider, model), row in rows.items():
        flag = flags.get(f"{provider}:{model}")
        if isinstance(flag, dict) and flag.get("vision") is True:
            row.vision = True
        _apply_openrouter(row, index)

    # 7. provider rollup
    usage_by_provider: dict[str, dict] = {}
    for row in rows.values():
        bucket = usage_by_provider.setdefault(
            row.provider, {"models": 0, "in_use": 0, "requests": 0, "cost": 0.0}
        )
        bucket["models"] += 1
        bucket["in_use"] += 1 if row.in_use else 0
        bucket["requests"] += row.requests
        bucket["cost"] += row.cost

    connections: dict[str, list] = {}
    for conn in snapshot.connections:
        connections.setdefault(conn.provider, []).append(
            {
                "name": conn.name,
                "auth_type": conn.auth_type,
                "active": conn.active,
                "priority": conn.priority,
            }
        )

    providers = []
    for provider in sorted(set(usage_by_provider) | set(connections)):
        bucket = usage_by_provider.get(
            provider, {"models": 0, "in_use": 0, "requests": 0, "cost": 0.0}
        )
        conns = connections.get(provider, [])
        providers.append(
            {
                "provider": provider,
                "models": bucket["models"],
                "in_use": bucket["in_use"],
                "requests": bucket["requests"],
                "cost": round(bucket["cost"], 6),
                "connections": conns,
                "active_connections": sum(1 for c in conns if c["active"]),
            }
        )

    warnings = list(snapshot.warnings)
    if not index:
        warnings.append("no OpenRouter models available: enrichment skipped")
    rows_sorted = sorted(
        rows.values(), key=lambda r: (-r.requests, r.provider, r.model)
    )
    return Inventory(rows=rows_sorted, providers=providers, combos=combos, warnings=warnings)
