from __future__ import annotations

from pathlib import Path

from conftest import CANARY

from nine_router_followup import inventory, render, sources


def _html(local_home: Path, or_models: dict, **kwargs) -> str:
    inv = inventory.build(sources.load_local(local_home), or_models)
    return render.build_html(inv, generated="2026-11-19T00:00:00Z", **kwargs)


def test_html_is_self_contained(local_home: Path, or_models: dict):
    html = _html(local_home, or_models)
    lowered = html.lower()
    assert lowered.startswith("<!doctype html>")
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "<script src" not in lowered
    assert "<link " not in lowered


def test_html_never_contains_secrets(local_home: Path, or_models: dict):
    html = _html(local_home, or_models)
    assert CANARY not in html


def test_html_keeps_data_out_of_markup(local_home: Path, or_models: dict):
    html = _html(local_home, or_models)
    assert 'type="application/json"' in html
    # the payload is escaped so it cannot close the script element early
    assert "</script><script>" not in html


def test_script_breakout_is_escaped():
    inv = inventory.Inventory(
        rows=[
            inventory.ModelRow(
                provider="evil",
                model="</script><script>alert(1)</script>",
                or_name="<!-- comment -->",
            )
        ]
    )
    html = render.build_html(inv, generated="x")
    assert "</script><script>alert(1)" not in html
    assert "<\\/script>" in html
    assert "<!-- comment" not in html


def test_output_is_deterministic(local_home: Path, or_models: dict):
    assert _html(local_home, or_models) == _html(local_home, or_models)


def test_document_references_the_product(local_home: Path, or_models: dict):
    html = _html(local_home, or_models, product="acme-router")
    assert "acme-router" in html
    assert "9router model inventory" in html


def test_refresh_button_explains_static_mode(local_home: Path, or_models: dict):
    html = _html(local_home, or_models)
    assert 'id="refresh"' in html
    assert 'id="refresh-hint"' in html
    assert "python3 -m nine_router_followup dashboard" in html
    assert 'fetch("/refresh"' in html


def test_payload_is_valid_json(local_home: Path, or_models: dict):
    import json
    import re

    html = _html(local_home, or_models)
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert match, "payload script not found"
    payload = json.loads(match.group(1).replace("<\\/", "</"))
    assert payload["summary"]["requests"] == 7
    assert payload["models"][0]["provider"] == "opencode"
