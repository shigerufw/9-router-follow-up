"""Fixture 9router home: a tiny catalog + sqlite DB with a leak canary."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

CANARY = "sk-CANARY-DO-NOT-LEAK-42"

OPENROUTER_MODELS = {
    "cohere/north-mini-code:free": {
        "id": "cohere/north-mini-code:free",
        "name": "Cohere: North Mini Code (free)",
        "context_length": 128000,
        "architecture": {"modality": "text->text", "input_modalities": ["text"]},
        "pricing": {"prompt": "0", "completion": "0"},
        "top_provider": {"max_completion_tokens": 8192},
    },
    "nvidia/nemotron-3.5-lightning-30b-a3b": {
        "id": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "name": "NVIDIA: Nemotron 3.5 Lightning",
        "context_length": 262144,
        "architecture": {"modality": "text+image->text", "input_modalities": ["text", "image"]},
        "pricing": {"prompt": "0.0000002", "completion": "0.0000006"},
        "top_provider": {"max_completion_tokens": 65536},
    },
    "meta/llama-guard-4-12b": {
        "id": "meta/llama-guard-4-12b",
        "name": "Meta: Llama Guard 4 12B",
        "context_length": 131072,
        "architecture": {"modality": "text->text", "input_modalities": ["text"]},
        "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
        "top_provider": {"max_completion_tokens": 4096},
    },
}

CATALOG = {
    "v": 2,
    "models": {
        "nvidia:nvidia/nemotron-3.5-lightning-30b-a3b": {"vision": True},
    },
    "providers": {
        "nvidia": {
            "nvidia/nemotron-3.5-lightning-30b-a3b": {
                "contextWindow": 262144,
                "maxOutput": 262144,
            },
            "deepseek-ai/deepseek-v4-pro": {
                "contextWindow": 163840,
                "maxOutput": 16384,
            },
        }
    },
}

SCHEMA = """
create table providerConnections (
  id text primary key, provider text not null, authType text not null, name text,
  email text, priority integer, isActive integer default 1, data text not null,
  createdAt text not null, updatedAt text not null
);
create table apiKeys (
  id text primary key, key text unique not null, name text, machineId text,
  isActive integer default 1, createdAt text not null, accessRestricted integer default 0,
  accessAllow text
);
create table usageHistory (
  id integer primary key autoincrement, timestamp text not null, provider text, model text,
  connectionId text, apiKey text, endpoint text, promptTokens integer default 0,
  completionTokens integer default 0, cost real default 0, status text, tokens text, meta text
);
create table combos (
  id text primary key, name text unique not null, kind text, models text not null,
  createdAt text not null, updatedAt text not null
);
create table kv (scope text not null, key text not null, value text not null, primary key (scope, key));
"""

USAGE = [
    ("2026-11-15T00:00:00Z", "opencode", "deepseek-v4.1-flash-free", 1000, 100, 0.01, "ok"),
    ("2026-11-16T00:00:00Z", "opencode", "deepseek-v4.1-flash-free", 2000, 200, 0.02, "ok"),
    ("2026-11-17T00:00:00Z", "opencode", "deepseek-v4.1-flash-free", 500, 50, 0.005, "ok"),
    ("2026-11-18T00:00:00Z", "nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", 100, 50, 0.0, "error"),
    ("2026-11-19T00:00:00Z", "nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", 100, 50, 0.0, "ok"),
    ("2026-11-19T01:00:00Z", "openrouter", "cohere/north-mini-code:free", 1, 2, 0.0, "ok"),
    ("2026-11-19T02:00:00Z", "nvidia", "llama-guard-4-12b", 5, 6, 0.0, "ok"),
]


@pytest.fixture()
def local_home(tmp_path: Path) -> Path:
    home = tmp_path / "9router"
    (home / "db").mkdir(parents=True)
    (home / "model-catalog.json").write_text(json.dumps(CATALOG))
    (home / "jwt-secret").write_text(CANARY)

    conn = sqlite3.connect(home / "db" / "data.sqlite")
    try:
        conn.executescript(SCHEMA)
        conn.executemany(
            "insert into providerConnections values (?,?,?,?,?,?,?,?,?,?)",
            [
                ("c1", "nvidia", "apikey", "nvidia-key", "", 1, 1, json.dumps({"apiKey": CANARY}), "", ""),
                ("c2", "openrouter", "apikey", "or-key", "", 1, 1, json.dumps({"apiKey": CANARY}), "", ""),
            ],
        )
        conn.execute(
            "insert into apiKeys values (?,?,?,?,?,?,?,?)",
            ("k1", CANARY, "machine", "m1", 1, "", 0, None),
        )
        conn.executemany(
            "insert into usageHistory (timestamp, provider, model, promptTokens, completionTokens, cost, status) "
            "values (?,?,?,?,?,?,?)",
            USAGE,
        )
        conn.execute(
            "insert into combos values (?,?,?,?,?,?)",
            (
                "b1",
                "t-combo",
                "",
                json.dumps(
                    [
                        "oc/deepseek-v4.1-flash-free",
                        "nvidia/nvidia/nemotron-3.5-lightning-30b-a3b",
                        "nvidia/missing-model",
                    ]
                ),
                "",
                "",
            ),
        )
        conn.executemany(
            "insert into kv values (?,?,?)",
            [
                (
                    "customModels",
                    "oc|deepseek-v4.1-flash-free|llm",
                    json.dumps({"providerAlias": "oc", "id": "deepseek-v4.1-flash-free", "type": "llm"}),
                ),
                (
                    "customModels",
                    "openrouter|cohere/north-mini-code:free|llm",
                    json.dumps({"providerAlias": "openrouter", "id": "cohere/north-mini-code:free", "type": "llm"}),
                ),
                ("disabledModels", "nvidia", json.dumps(["deepseek-ai/deepseek-v4-pro"])),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return home


@pytest.fixture()
def or_models() -> dict:
    return OPENROUTER_MODELS
