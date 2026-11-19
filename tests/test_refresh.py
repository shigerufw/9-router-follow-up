from __future__ import annotations

from pathlib import Path

import pytest

from conftest import OPENROUTER_MODELS

from nine_router_followup import cli, openrouter, refresh


def _cache(tmp_path: Path, fetched_at: float = 0) -> Path:
    path = tmp_path / "cache.json"
    openrouter.write_cache(path, OPENROUTER_MODELS, fetched_at)
    return path


def test_generate_writes_report(tmp_path: Path, local_home: Path):
    out = tmp_path / "dist" / "models.html"
    report = refresh.generate(
        out,
        home=local_home,
        cache=_cache(tmp_path),
        offline=True,
        generated="2026-01-01T00:00:00Z",
    )

    assert out.is_file()
    assert report.generated == "2026-01-01T00:00:00Z"
    assert report.summary["models"] > 0
    assert report.summary["requests"] == 7
    assert "2026-01-01T00:00:00Z" in out.read_text()
    assert not list(out.parent.glob(".*.tmp"))


def test_failure_leaves_previous_report_untouched(tmp_path: Path, local_home: Path, monkeypatch):
    out = tmp_path / "models.html"
    out.write_text("PREVIOUS")

    def boom(*_args, **_kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(refresh.render, "build_html", boom)
    with pytest.raises(RuntimeError):
        refresh.generate(out, home=local_home, cache=_cache(tmp_path), offline=True)

    assert out.read_text() == "PREVIOUS"
    assert not list(tmp_path.glob(".*.tmp"))


def test_concurrent_refresh_is_busy(tmp_path: Path, local_home: Path):
    out = tmp_path / "models.html"
    handle = refresh.acquire_lock(out)
    try:
        with pytest.raises(refresh.Busy):
            refresh.generate(out, home=local_home, cache=_cache(tmp_path), offline=True)
        assert not out.exists()
    finally:
        handle.close()

    # the OS releases the lock when the handle closes
    report = refresh.generate(out, home=local_home, cache=_cache(tmp_path), offline=True)
    assert report.path == out
    assert out.is_file()


def test_cli_skips_when_busy(tmp_path: Path, local_home: Path, capsys):
    out = tmp_path / "models.html"
    handle = refresh.acquire_lock(out)
    try:
        code = cli.main(
            [
                "dashboard",
                "--home",
                str(local_home),
                "--cache",
                str(_cache(tmp_path)),
                "--out",
                str(out),
                "--offline",
                "--skip-if-busy",
            ]
        )
    finally:
        handle.close()

    assert code == 0
    assert "skipped" in capsys.readouterr().out
    assert not out.exists()


def test_cli_busy_without_skip_fails_loudly(tmp_path: Path, local_home: Path, capsys):
    out = tmp_path / "models.html"
    handle = refresh.acquire_lock(out)
    try:
        code = cli.main(
            [
                "dashboard",
                "--home",
                str(local_home),
                "--cache",
                str(_cache(tmp_path)),
                "--out",
                str(out),
                "--offline",
            ]
        )
    finally:
        handle.close()

    assert code == 3
    assert "skip-if-busy" in capsys.readouterr().err
