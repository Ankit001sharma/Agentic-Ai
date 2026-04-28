"""Minimal code sandbox: POST /run { code } -> { result, stdout } (subprocess, 20s max)."""

from __future__ import annotations

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


def run_python(code: str, timeout: float) -> dict[str, Any]:
    c = (code or "")[:32_000]
    try:
        r = subprocess.run(
            [sys.executable, "-c", c],
            capture_output=True,
            text=True,
            timeout=min(float(timeout or 5), 20.0),
            env={"PATH": "/usr/bin", "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0"},
        )
        out = (r.stdout or r.stderr or "")[:8000]
        return {"ok": r.returncode == 0, "stdout": out, "returncode": r.returncode, "result": out}
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "timeout", "returncode": -1, "result": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "stdout": str(e)[:2000], "returncode": -1, "result": str(e)}


class H(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/run", "/run/"):
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        body = (self.rfile.read(n) or b"{}").decode("utf-8", errors="replace")
        try:
            d: dict = json.loads(body) if body.strip() else {}
        except Exception:  # noqa: BLE001
            d = {}
        code = str(d.get("code", ""))
        timeout = float(d.get("timeout", 5))
        r = run_python(code, timeout)
        b = json.dumps(r).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *args) -> None:  # noqa: ANN001
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8888), H).serve_forever()
