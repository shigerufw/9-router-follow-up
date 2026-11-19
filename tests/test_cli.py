from __future__ import annotations

from pathlib import Path

from conftest import CANARY

from nine_router_followup import cli, openrouter


def test_dashboard_command_writes_html(tmp_path: Path, local_home: Path):
    cache = tmp_path / "cache.json"
    openrouter.write_cache(cache, {"nvidia/nemotron-3.5-lightning-30b-a3b": {}}, 0)
    out = tmp_path / "dist" / "models.html"

    code = cli.main(
        [
            "dashboard",
            "--home",
            str(local_home),
            "--cache",
            str(cache),
            "--out",
            str(out),
            "--offline",
            "--generated",
            "2026-11-19T12:00:00Z",
        ]
    )

    assert code == 0
    assert out.is_file()
    html = out.read_text()
    assert "2026-11-19T12:00:00Z" in html
    assert CANARY not in html


def test_missing_home_still_produces_a_page(tmp_path: Path):
    out = tmp_path / "models.html"
    code = cli.main(
        [
            "dashboard",
            "--home",
            str(tmp_path / "nope"),
            "--cache",
            str(tmp_path / "cache.json"),
            "--out",
            str(out),
            "--offline",
            "--generated",
            "2026-01-01T00:00:00Z",
        ]
    )
    assert code == 0
    assert out.is_file()
    assert "no 9router database" in out.read_text()


def test_requires_a_subcommand():
    import pytest

    with pytest.raises(SystemExit):
        cli.main([])
