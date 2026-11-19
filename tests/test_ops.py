from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_refresh_script_is_executable():
    assert os.access(ROOT / "ops" / "refresh.sh", os.X_OK)


def test_refresh_script_runs_and_logs(tmp_path: Path, local_home: Path):
    out = tmp_path / "out.html"
    log = tmp_path / "refresh.log"
    env = dict(
        os.environ,
        REFRESH_OUT=str(out),
        REFRESH_LOG=str(log),
        REFRESH_ARGS=" ".join(
            [
                "--offline",
                "--home",
                shlex.quote(str(local_home)),
                "--cache",
                shlex.quote(str(tmp_path / "missing-cache.json")),
            ]
        ),
    )

    result = subprocess.run(
        [str(ROOT / "ops" / "refresh.sh")], capture_output=True, text=True, env=env
    )

    assert result.returncode == 0, result.stderr
    assert out.is_file()
    assert "wrote" in log.read_text()


def test_refresh_script_propagates_failure(tmp_path: Path):
    log = tmp_path / "refresh.log"
    env = dict(
        os.environ,
        REFRESH_OUT=str(tmp_path / "out.html"),
        REFRESH_LOG=str(log),
        REFRESH_ARGS="--bogus-flag",
    )

    result = subprocess.run(
        [str(ROOT / "ops" / "refresh.sh")], capture_output=True, text=True, env=env
    )

    assert result.returncode != 0
    assert log.is_file()


def test_schedule_templates_exist():
    plist = ROOT / "ops" / "launchd" / "com.9routerfollowup.refresh.plist.template"
    cron = ROOT / "ops" / "cron.example"
    assert plist.is_file() and cron.is_file()
    assert "__REPO__" in plist.read_text()
    assert "StartInterval" in plist.read_text()
    assert "refresh.sh" in cron.read_text()
