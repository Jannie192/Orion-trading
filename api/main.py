from __future__ import annotations

import importlib.util
import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"

_ROUTES = {
    "/api/paper-scan": "paper-scan.py",
    "/api/paper-state": "paper-state.py",
    "/api/scan": "scan.py",
    "/api/backtest": "backtest.py",
    "/api/backtest-batch": "backtest-batch.py",
}

_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}

def _load_handler(filename: str):
    path = API_DIR / filename
    spec = importlib.util.spec_from_file_location(f"orion_api_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load API handler: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler

def _serve_static(request_handler: BaseHTTPRequestHandler, route: str) -> bool:
    entry = _STATIC.get(route)
    if entry is None:
        return False
    filename, content_type = entry
    path = ROOT / filename
    payload = path.read_bytes()
    request_handler.send_response(200)
    request_handler.send_header("Content-Type", content_type)
    request_handler.send_header("Cache-Control", "no-store, max-age=0")
    request_handler.send_header("Content-Length", str(len(payload)))
    request_handler.end_headers()
    request_handler.wfile.write(payload)
    return True

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path

        if _serve_static(self, route):
            return

        if route == "/api/main":
            key = parse_qs(parsed.query).get("route", [""])[0]
            route = f"/api/{key}" if key else route

        filename = _ROUTES.get(route)
        if filename is None:
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"error":"Not found"}')
            return

        target = _load_handler(filename)
        target.do_GET(self)
