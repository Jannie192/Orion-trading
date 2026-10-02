from __future__ import annotations

import importlib.util
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"

_ROUTES = {
    "/api/paper-scan": "paper-scan.py",
    "/api/paper-state": "paper-state.py",
    "/api/scan": "scan.py",
}

_STATIC = {
    "/": ("dashboard/index.html", "text/html; charset=utf-8"),
    "/styles.css": ("dashboard/styles.css", "text/css; charset=utf-8"),
    "/app.js": ("dashboard/app.js", "application/javascript; charset=utf-8"),
}


def _load_handler(filename: str):
    path = API_DIR / filename
    spec = importlib.util.spec_from_file_location(f"orion_api_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load API handler: {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.handler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        query_route = parse_qs(parsed.query).get("route", [None])[0]

        static = _STATIC.get(route)
        if static:
            path = ROOT / static[0]
            try:
                body = path.read_bytes()
            except OSError:
                self.send_response(404)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(b'{"error":"Dashboard asset not found"}')
                return
            self.send_response(200)
            self.send_header("Content-Type", static[1])
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return

        filename = _ROUTES.get(route) or _ROUTES.get(f"/api/{query_route}")
        if filename is None:
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"error":"Not found"}')
            return

        target = _load_handler(filename)
        target.do_GET(self)
