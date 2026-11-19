from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from conftest import OPENROUTER_MODELS

from nine_router_followup import openrouter, refresh, serve


@pytest.fixture()
def server(tmp_path: Path, local_home: Path):
    cache = tmp_path / "cache.json"
    openrouter.write_cache(cache, OPENROUTER_MODELS, 0)
    out = tmp_path / "dist" / "models.html"
    srv = serve.make_server(port=0, out=out, home=local_home, cache=cache, offline=True)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv, out
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=5)


def _url(srv, path: str = "/") -> str:
    return f"http://127.0.0.1:{srv.server_port}{path}"


def test_binds_loopback_only(server):
    srv, _ = server
    assert srv.server_address[0] == "127.0.0.1"


def test_health(server):
    srv, _ = server
    with urllib.request.urlopen(_url(srv, "/health")) as response:
        assert response.status == 200
        assert json.loads(response.read())["ok"] is True


def test_index_generates_and_serves(server):
    srv, out = server
    with urllib.request.urlopen(_url(srv)) as response:
        html = response.read().decode()
        assert response.status == 200
    assert 'id="refresh"' in html
    assert out.is_file()


def test_refresh_endpoint_regenerates(server):
    srv, out = server
    urllib.request.urlopen(_url(srv)).read()
    before = out.stat().st_mtime_ns

    request = urllib.request.Request(_url(srv, "/refresh"), method="POST")
    with urllib.request.urlopen(request) as response:
        payload = json.loads(response.read())

    assert response.status == 200
    assert payload["ok"] is True
    assert payload["summary"]["models"] > 0
    assert payload["generated"]
    assert out.stat().st_mtime_ns >= before


def test_refresh_while_locked_returns_409(server):
    srv, out = server
    handle = refresh.acquire_lock(out)
    try:
        request = urllib.request.Request(_url(srv, "/refresh"), method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 409
    finally:
        handle.close()


def test_unknown_paths_are_404(server):
    srv, _ = server
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(_url(srv, "/nope"))
    assert error.value.code == 404
