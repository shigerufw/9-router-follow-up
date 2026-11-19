"""Read-only readers for a local 9router install.

Nothing here writes to 9router, and credential-bearing columns are never
selected: ``providerConnections.data``, the ``apiKeys`` table and
``~/.9router/jwt-secret`` are off limits by design.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

DEFAULT_HOME = Path.home() / ".9router"

# 9router reports the opencode provider as "opencode" in usage but as the
# "oc" alias in custom models and combo ids.
ALIASES = {"oc": "opencode"}

# Statuses 9router writes for a request that completed.
OK_STATUSES = {"ok", "success", "completed"}


def normalize_provider(name: str) -> str:
    name = (name or "").strip()
    return ALIASES.get(name, name) or name


@dataclass(frozen=True)
class Connection:
    provider: str
    name: str
    auth_type: str
    active: bool
    priority: int | None


@dataclass(frozen=True)
class Usage:
    provider: str
    model: str
    requests: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    errors: int
    first_seen: str
    last_seen: str


@dataclass(frozen=True)
class Combo:
    name: str
    kind: str
    models: tuple[str, ...]


@dataclass
class Snapshot:
    connections: list[Connection] = field(default_factory=list)
    usage: list[Usage] = field(default_factory=list)
    combos: list[Combo] = field(default_factory=list)
    # provider alias -> [(model id, kind)], e.g. "oc" -> [("deepseek-...", "llm")]
    custom_models: dict[str, list[tuple[str, str]]] = field(default_factory=dict)
    # provider alias -> disabled model ids
    disabled_models: dict[str, list[str]] = field(default_factory=dict)
    catalog: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _read_json(path: Path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def open_readonly(db_path: Path) -> sqlite3.Connection | None:
    """Open the 9router DB with ``mode=ro``; return None when unavailable."""
    path = Path(db_path)
    if not path.is_file():
        return None
    try:
        return sqlite3.connect(f"file:{quote(path.as_posix())}?mode=ro", uri=True)
    except sqlite3.Error:
        return None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type='table' and name=?", (name,)
    ).fetchone()
    return row is not None


def read_connections(conn: sqlite3.Connection) -> list[Connection]:
    """Connections without the ``data`` blob (it holds API keys)."""
    rows = conn.execute(
        "select provider, coalesce(authType,''), coalesce(name,''), "
        "coalesce(isActive,1), priority from providerConnections "
        "order by provider, priority"
    ).fetchall()
    return [
        Connection(
            provider=normalize_provider(provider),
            name=name,
            auth_type=auth_type,
            active=bool(active),
            priority=priority,
        )
        for provider, auth_type, name, active, priority in rows
    ]


def read_usage(conn: sqlite3.Connection) -> list[Usage]:
    placeholders = ",".join("?" for _ in OK_STATUSES)
    rows = conn.execute(
        "select provider, model, count(*), "
        "coalesce(sum(promptTokens),0), coalesce(sum(completionTokens),0), "
        "coalesce(sum(cost),0.0), "
        f"coalesce(sum(case when lower(coalesce(status,'')) in ({placeholders}) "
        "then 0 else 1 end),0), "
        "coalesce(min(timestamp),''), coalesce(max(timestamp),'') "
        "from usageHistory group by provider, model",
        tuple(sorted(OK_STATUSES)),
    ).fetchall()
    usage: list[Usage] = []
    for (
        provider,
        model,
        requests,
        prompt_tokens,
        completion_tokens,
        cost,
        errors,
        first_seen,
        last_seen,
    ) in rows:
        # A malformed row must not become a phantom model named "None".
        if not (provider or "").strip() or not (model or "").strip():
            continue
        usage.append(
            Usage(
                provider=normalize_provider(provider),
                model=model.strip(),
                requests=requests,
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                cost=float(cost),
                errors=int(errors),
                first_seen=first_seen,
                last_seen=last_seen,
            )
        )
    return usage


def read_combos(conn: sqlite3.Connection) -> list[Combo]:
    combos = []
    for name, kind, models in conn.execute(
        "select name, coalesce(kind,''), models from combos order by name"
    ):
        try:
            parsed = json.loads(models)
        except (TypeError, ValueError):
            parsed = []
        if not isinstance(parsed, list):
            parsed = []
        combos.append(
            Combo(
                name=name,
                kind=kind,
                models=tuple(str(m) for m in parsed if isinstance(m, str)),
            )
        )
    return combos


def _read_kv(conn: sqlite3.Connection, scope: str) -> list[tuple[str, str]]:
    return conn.execute(
        "select key, value from kv where scope = ?", (scope,)
    ).fetchall()


def read_custom_models(conn: sqlite3.Connection) -> dict[str, list[tuple[str, str]]]:
    """``kv/customModels`` keys look like ``provider|model|kind``."""
    out: dict[str, list[tuple[str, str]]] = {}
    for key, value in _read_kv(conn, "customModels"):
        payload = _parse_obj(value)
        provider = str(payload.get("providerAlias") or key.split("|")[0])
        model = str(payload.get("id") or (key.split("|")[1] if "|" in key else ""))
        kind = str(payload.get("type") or (key.split("|")[-1] if "|" in key else "llm"))
        if model:
            out.setdefault(provider, []).append((model, kind))
    return out


def read_disabled_models(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for key, value in _read_kv(conn, "disabledModels"):
        parsed = _parse_obj(value) if value.strip().startswith("{") else _parse_list(value)
        if isinstance(parsed, list):
            out[key] = [str(m) for m in parsed if isinstance(m, str)]
    return out


def _parse_obj(text) -> dict:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_list(text) -> list:
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def load_local(home: Path | str = DEFAULT_HOME) -> Snapshot:
    """Read the whole local snapshot; missing pieces degrade to empty lists."""
    home = Path(home).expanduser()
    snap = Snapshot()

    catalog = _read_json(home / "model-catalog.json", {})
    snap.catalog = catalog if isinstance(catalog, dict) else {}
    if not snap.catalog:
        snap.warnings.append(f"no model catalog found at {home / 'model-catalog.json'}")

    conn = open_readonly(home / "db" / "data.sqlite")
    if conn is None:
        snap.warnings.append(f"no 9router database found at {home / 'db' / 'data.sqlite'}")
        return snap

    try:
        for name, reader, target in (
            ("providerConnections", read_connections, "connections"),
            ("usageHistory", read_usage, "usage"),
            ("combos", read_combos, "combos"),
        ):
            if not _table_exists(conn, name):
                snap.warnings.append(f"table {name} missing from 9router database")
                continue
            try:
                setattr(snap, target, reader(conn))
            except sqlite3.Error as e:
                snap.warnings.append(f"could not read {name}: {e}")
        if _table_exists(conn, "kv"):
            try:
                snap.custom_models = read_custom_models(conn)
                snap.disabled_models = read_disabled_models(conn)
            except sqlite3.Error as e:
                snap.warnings.append(f"could not read kv: {e}")
        else:
            snap.warnings.append("table kv missing from 9router database")
    finally:
        conn.close()

    return snap
