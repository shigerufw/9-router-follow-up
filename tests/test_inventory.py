from __future__ import annotations

from pathlib import Path

import pytest

from nine_router_followup import inventory, sources


def _build(local_home: Path, or_models: dict) -> inventory.Inventory:
    return inventory.build(sources.load_local(local_home), or_models)


def _row(inv: inventory.Inventory, provider: str, model: str) -> inventory.ModelRow:
    for row in inv.rows:
        if row.provider == provider and row.model == model:
            return row
    raise AssertionError(f"missing row {provider}/{model}")


def test_usage_is_aggregated_per_model(local_home: Path, or_models: dict):
    row = _row(_build(local_home, or_models), "opencode", "deepseek-v4.1-flash-free")
    assert row.requests == 3
    assert row.prompt_tokens == 3500
    assert row.completion_tokens == 350
    assert abs(row.cost - 0.035) < 1e-9
    assert row.errors == 0
    assert row.first_seen == "2026-11-15T00:00:00Z"
    assert row.last_seen == "2026-11-17T00:00:00Z"


def test_errors_and_last_seen(local_home: Path, or_models: dict):
    row = _row(_build(local_home, or_models), "nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b")
    assert row.requests == 2
    assert row.errors == 1
    assert row.last_seen == "2026-11-19T00:00:00Z"


def test_disabled_catalogue_model_is_listed_but_off(local_home: Path, or_models: dict):
    inv = _build(local_home, or_models)
    row = _row(inv, "nvidia", "deepseek-ai/deepseek-v4-pro")
    assert row.enabled is False
    assert row.requests == 0
    assert row.context_window == 163840


def test_custom_models_are_enabled(local_home: Path, or_models: dict):
    inv = _build(local_home, or_models)
    row = _row(inv, "opencode", "deepseek-v4.1-flash-free")
    assert row.enabled is True


def test_combos_record_membership_and_availability(local_home: Path, or_models: dict):
    inv = _build(local_home, or_models)
    combo = inv.combos[0]
    assert combo["name"] == "t-combo"
    members = {m["raw"]: m for m in combo["members"]}
    assert members["oc/deepseek-v4.1-flash-free"]["available"] is True
    assert members["nvidia/nvidia/nemotron-3.5-lightning-30b-a3b"]["available"] is True
    assert members["nvidia/missing-model"]["available"] is False
    assert _row(inv, "opencode", "deepseek-v4.1-flash-free").in_combos == ("t-combo",)


def test_openrouter_enrichment(local_home: Path, or_models: dict):
    inv = _build(local_home, or_models)

    nvidia = _row(inv, "nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b")
    assert nvidia.or_id == "nvidia/nemotron-3.5-lightning-30b-a3b"
    assert nvidia.or_name.startswith("NVIDIA:")
    assert nvidia.prompt_price == pytest.approx(0.2)
    assert nvidia.completion_price == pytest.approx(0.6)
    assert nvidia.vision is True
    assert nvidia.context == 262144

    cohere = _row(inv, "openrouter", "cohere/north-mini-code:free")
    assert cohere.or_id == "cohere/north-mini-code:free"
    assert cohere.prompt_price == 0.0


def test_tail_match_and_unmatched(local_home: Path, or_models: dict):
    inv = _build(local_home, or_models)
    guard = _row(inv, "nvidia", "llama-guard-4-12b")
    assert guard.or_id == "meta/llama-guard-4-12b"
    assert guard.or_match == "tail"

    unknown = _row(inv, "opencode", "deepseek-v4.1-flash-free")
    assert unknown.or_id is None
    assert unknown in inv.unmatched


def test_tail_match_is_not_labelled_variant():
    index = {"meta-llama/llama-guard-4-12b": {}}
    or_id, kind = inventory.match_openrouter("nvidia", "meta/llama-guard-4-12b", index)
    assert or_id == "meta-llama/llama-guard-4-12b"
    assert kind == "tail"


def test_size_tag_fuzzy_match():
    index = {"nvidia/nemotron-3.5-lightning": {}, "nvidia/nemotron-3.5-lightning:free": {}}
    or_id, kind = inventory.match_openrouter(
        "nvidia", "nvidia/nemotron-3.5-lightning-30b-a3b", index
    )
    assert or_id == "nvidia/nemotron-3.5-lightning"
    assert kind == "fuzzy"


def test_variant_suffix_match():
    index = {"deepseek/deepseek-v4.1-flash": {}}
    or_id, kind = inventory.match_openrouter("opencode", "deepseek-v4.1-flash-free", index)
    assert or_id == "deepseek/deepseek-v4.1-flash"
    assert kind == "variant"


def test_match_openrouter_prefers_provider_and_rejects_ambiguity():
    index = {"alpha/foo": {}, "beta/foo": {}}
    assert inventory.match_openrouter("alpha", "foo", index) == ("alpha/foo", "provider")
    assert inventory.match_openrouter("acme", "foo", index) == (None, "ambiguous")
    assert inventory.match_openrouter("acme", "nothing-like-it", index) == (None, "no match")


def test_summary_totals(local_home: Path, or_models: dict):
    summary = _build(local_home, or_models).summary()
    assert summary["requests"] == 7
    assert summary["providers"] == 3
    assert summary["connected"] == 2
    assert summary["combos"] == 1
    assert summary["models_in_use"] == 4
    assert summary["unmatched"] >= 1
