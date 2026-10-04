from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.paper_state_api import PaperStateAdapter
from orion_trading.supabase_paper_store import SupabasePaperStore


def snapshot():
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        store = SupabasePaperStore()
        snap = store.snapshot()
        snap["recent_trades"] = store.closed_trades()[:25]
        return snap
    return {
        **PaperStateAdapter().snapshot(),
        "persistence": "memory",
        "warning": "Supabase persistence is not configured on this deployment.",
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = json.dumps(snapshot(), separators=(",", ":")).encode("utf-8")
            status = 200
        except Exception as exc:
            payload = json.dumps({
                "mode": "paper",
                "live_trading_enabled": False,
                "error": str(exc),
            }, separators=(",", ":")).encode("utf-8")
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
