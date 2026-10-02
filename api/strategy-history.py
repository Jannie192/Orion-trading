from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.supabase_strategy_store import SupabaseStrategyStore


def _json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            store = SupabaseStrategyStore()
            q = parse_qs(urlparse(self.path).query)
            limit = int(q.get("limit", ["50"])[0])
            _json(self, {"mode":"research","live_trading_enabled":False,"versions":store.versions(),"experiments":store.experiments(limit)})
        except Exception as exc:
            _json(self, {"error":str(exc),"mode":"research","live_trading_enabled":False}, 500)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            store = SupabaseStrategyStore()
            action = body.get("action")
            if action == "version":
                required = ("name","version","instrument","timeframe","days","risks","stops","rewards")
                if any(k not in body for k in required):
                    raise ValueError("MISSING_STRATEGY_VERSION_FIELDS")
                row = store.create_version({k: body[k] for k in required} | {"status": body.get("status","DRAFT")})
                return _json(self, {"version":row,"mode":"research","live_trading_enabled":False})
            if action == "experiment":
                required = ("strategy_name","strategy_version","instrument","timeframe","days","grid","validation","results")
                if any(k not in body for k in required):
                    raise ValueError("MISSING_EXPERIMENT_FIELDS")
                row = store.create_experiment({k: body[k] for k in required})
                return _json(self, {"experiment":row,"mode":"research","live_trading_enabled":False})
            if action == "promote":
                row = store.promote(str(body.get("strategy_id","")), str(body.get("status","")))
                return _json(self, {"version":row,"mode":"research","live_trading_enabled":False})
            raise ValueError("UNKNOWN_STRATEGY_ACTION")
        except Exception as exc:
            _json(self, {"error":str(exc),"mode":"research","live_trading_enabled":False}, 400)
