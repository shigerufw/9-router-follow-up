from __future__ import annotations

import json
from pathlib import Path

from nine_router_followup import openrouter

TTL = openrouter.TTL_S


def _boom():
    raise AssertionError("fetcher must not be called")


def test_network_fetch_writes_cache(tmp_path: Path):
    cache = tmp_path / "cache.json"
    result = openrouter.load(cache, fetcher=lambda: [{"id": "a/b"}], now=1000)

    assert result.source == "network"
    assert "a/b" in result.models
    stored = json.loads(cache.read_text())
    assert stored["fetched_at"] == 1000
    assert "a/b" in stored["models"]


def test_fresh_cache_skips_the_network(tmp_path: Path):
    cache = tmp_path / "cache.json"
    openrouter.write_cache(cache, {"x/y": {"id": "x/y"}}, 1000)

    result = openrouter.load(cache, fetcher=_boom, now=1000 + TTL / 2)
    assert result.source == "cache"
    assert "x/y" in result.models


def test_stale_cache_is_used_when_fetch_fails(tmp_path: Path):
    cache = tmp_path / "cache.json"
    openrouter.write_cache(cache, {"x/y": {"id": "x/y"}}, 0)

    def offline():
        raise OSError("no network")

    result = openrouter.load(cache, fetcher=offline, now=10**9)
    assert result.source == "cache"
    assert "x/y" in result.models
    assert result.warning and "using cached models" in result.warning


def test_offline_never_fetches(tmp_path: Path):
    cache = tmp_path / "cache.json"
    openrouter.write_cache(cache, {"x/y": {}}, 0)

    result = openrouter.load(cache, offline=True, fetcher=_boom, now=10**9)
    assert result.source == "cache"


def test_offline_without_cache_degrades(tmp_path: Path):
    result = openrouter.load(tmp_path / "missing.json", offline=True, fetcher=_boom)
    assert result.source == "none"
    assert not result
    assert result.warning


def test_refresh_forces_a_fetch(tmp_path: Path):
    cache = tmp_path / "cache.json"
    openrouter.write_cache(cache, {"old/one": {}}, 1000)
    calls = []

    def fetcher():
        calls.append(1)
        return [{"id": "new/two"}]

    result = openrouter.load(cache, refresh=True, fetcher=fetcher, now=1001)
    assert calls == [1]
    assert result.source == "network"
    assert set(result.models) == {"new/two"}


def test_corrupt_cache_is_ignored(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text("{not json")
    result = openrouter.load(cache, fetcher=lambda: [{"id": "a/b"}], now=1000)
    assert result.source == "network"
    assert "a/b" in result.models
