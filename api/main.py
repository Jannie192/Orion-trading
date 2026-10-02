from __future__ import annotations

import importlib.util
from http.server import BaseHTTPRequestHandler
from pathlib import Path

API_DIR = Path(__file__).resolve().parent

_ROUTES = {
    "/api/paper-scan": "paper-scan.py",
    "/api/paper-state": "paper-state.py",
    "/api/scan": "scan.py",
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
        route = self.path.split("?", 1)[0]
        filename = _ROUTES.get(route)
        if filename is None:
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(b'{"error":"Not found"}')
            return

        target = _load_handler(filename)
        target.do_GET(self)
