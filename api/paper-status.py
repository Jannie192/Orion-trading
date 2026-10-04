from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.supabase_paper_store import SupabasePaperStore


def read_status():
    store = SupabasePaperStore()
    snapshot = store.snapshot()
    return {
        "mode": "paper",
        "live_trading_enabled": False,
        "account": snapshot.get("account", {}),
        "performance": snapshot.get("performance", {}),
        "open_positions": snapshot.get("open_positions", []),
        "recent_trades": store.closed_trades()[:25],
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = json.dumps(read_status(), separators=(",", ":")).encode()
            code = 200
        except Exception as exc:
            payload = json.dumps({
                "mode": "paper",
                "live_trading_enabled": False,
                "error": str(exc),
                "account": {},
                "performance": {},
                "open_positions": [],
                "recent_trades": [],
            }, separators=(",", ":")).encode()
            code = 502
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
