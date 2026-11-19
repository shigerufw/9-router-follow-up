from __future__ import annotations

from pathlib import Path

from conftest import CANARY, OPENROUTER_MODELS

from nine_router_followup import sources


def test_loads_local_snapshot(local_home: Path):
    snap = sources.load_local(local_home)

    providers = {c.provider for c in snap.connections}
    assert providers == {"nvidia", "openrouter"}
    assert all(c.active for c in snap.connections)
    assert len(snap.usage) == 4  # 7 requests grouped into 4 provider/model pairs
    assert snap.combos[0].name == "t-combo"
    assert snap.custom_models["oc"] == [("deepseek-v4.1-flash-free", "llm")]
    assert snap.disabled_models["nvidia"] == ["deepseek-ai/deepseek-v4-pro"]


def test_credentials_are_never_read(local_home: Path):
    snap = sources.load_local(local_home)
    for conn in snap.connections:
        assert not hasattr(conn, "data")
        assert CANARY not in repr(conn)
    assert CANARY not in repr(snap)


def test_missing_home_degrades_with_warnings(tmp_path: Path):
    snap = sources.load_local(tmp_path / "nope")
    assert snap.usage == [] and snap.connections == []
    assert snap.warnings and "model catalog" in snap.warnings[0]


def test_opencode_alias_is_normalized(local_home: Path):
    snap = sources.load_local(local_home)
    assert {u.provider for u in snap.usage} == {"opencode", "nvidia", "openrouter"}


def test_malformed_usage_rows_are_dropped(local_home: Path):
    snap = sources.load_local(local_home)
    assert len(snap.usage) == 4
    for usage in snap.usage:
        assert usage.provider.strip()
        assert usage.model.strip()
        assert usage.model not in {"None", "  "}


def test_catalog_is_loaded(local_home: Path):
    snap = sources.load_local(local_home)
    assert "nvidia" in snap.catalog["providers"]
    assert snap.catalog["models"]["nvidia:nvidia/nemotron-3.5-lightning-30b-a3b"]["vision"] is True


def test_openrouter_fixture_is_consistent():
    assert set(OPENROUTER_MODELS) == {
        "cohere/north-mini-code:free",
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "meta/llama-guard-4-12b",
    }
