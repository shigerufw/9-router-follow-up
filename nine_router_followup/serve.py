"""Local dashboard server: serves the generated page and refreshes it on demand.

Opt-in only (``python3 -m nine_router_followup serve``), loopback-bound, with no
parameters: ``POST /refresh`` re-runs the same in-process generator the CLI uses.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import refresh as refresh_mod


def make_server(
    *,
    port: int = 4780,
    host: str = "127.0.0.1",
    out: Path | str = refresh_mod.DEFAULT_OUT,
    home: Path | str | None = None,
    cache: Path | str | None = None,
    offline: bool = False,
    force_fetch: bool = False,
    verbose: bool = False,
) -> ThreadingHTTPServer:
    out = Path(out)
    state = {"last": None, "error": None}

    class Handler(BaseHTTPRequestHandler):
        server_version = "9router-followup"

        def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
            if verbose:
                super().log_message(fmt, *args)

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict) -> None:
            self._send(code, json.dumps(payload).encode(), "application/json")

        def _regenerate(self) -> refresh_mod.Report:
            report = refresh_mod.generate(
                out,
                home=home,
                cache=cache,
                offline=offline,
                force_fetch=force_fetch,
            )
            state["last"] = report.generated
            state["error"] = None
            return report

        def do_GET(self):  # noqa: N802 - stdlib signature
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                if not out.exists():
                    try:
                        self._regenerate()
                    except Exception as e:  # noqa: BLE001 - report it, keep serving
                        state["error"] = str(e)
                if out.exists():
                    self._send(HTTPStatus.OK, out.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        f"<h1>No report yet</h1><p>{state['error']}</p>".encode(),
                        "text/html; charset=utf-8",
                    )
                return
            if path == "/health":
                self._json(
                    HTTPStatus.OK,
                    {"ok": True, "generated": state["last"], "error": state["error"]},
                )
                return
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

        def do_POST(self):  # noqa: N802 - stdlib signature
            if urlparse(self.path).path != "/refresh":
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
                return
            try:
                report = self._regenerate()
            except refresh_mod.Busy as e:
                self._json(HTTPStatus.CONFLICT, {"ok": False, "error": str(e)})
                return
            except Exception as e:  # noqa: BLE001 - surface the message to the page
                state["error"] = str(e)
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(e)})
                return
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "generated": report.generated,
                    "openrouter_source": report.openrouter_source,
                    "summary": report.summary,
                    "warnings": report.warnings,
                },
            )

    return ThreadingHTTPServer((host, port), Handler)


def serve(
    *,
    port: int = 4780,
    host: str = "127.0.0.1",
    out: Path | str = refresh_mod.DEFAULT_OUT,
    home: Path | str | None = None,
    cache: Path | str | None = None,
    offline: bool = False,
    force_fetch: bool = False,
    verbose: bool = False,
) -> int:
    out = Path(out)
    try:
        report = refresh_mod.generate(
            out, home=home, cache=cache, offline=offline, force_fetch=force_fetch
        )
        print(f"report: {report.path} ({report.summary.get('models', '?')} models)")
    except refresh_mod.Busy as e:
        print(f"warning: {e}; serving the existing report")
    except Exception as e:  # noqa: BLE001 - startup must not prevent serving
        print(f"warning: initial refresh failed: {e}")

    server = make_server(
        port=port,
        host=host,
        out=out,
        home=home,
        cache=cache,
        offline=offline,
        force_fetch=force_fetch,
        verbose=verbose,
    )
    print(f"serving on http://{host}:{server.server_port}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0
