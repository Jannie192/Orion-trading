from __future__ import annotations

import importlib.util
import json
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
API_DIR = ROOT / "api"
import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.supabase_strategy_store import SupabaseStrategyStore

def _load_batch():
    path = API_DIR / "backtest-batch.py"
    spec = importlib.util.spec_from_file_location("orion_batch_engine", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("BATCH_ENGINE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _json(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            instrument = str(body.get("instrument", "BTCUSDT"))
            timeframe = str(body.get("timeframe", "H1"))
            days = int(body.get("days", 90))

            # Controlled research defaults: 27 runs around a baseline.
            # The engine never promotes a strategy and never enables live execution.
            risk = str(body.get("risks", "0.25,0.5,0.75"))
            stops = str(body.get("stops", "1,1.5,2"))
            rewards = str(body.get("rewards", "1.5,2,3"))
            name = str(body.get("strategy_name", "ORION Auto Research"))
            version = str(body.get("strategy_version", "AUTO"))

            batch = _load_batch()
            result = batch.run(instrument, timeframe, days, risk, stops, rewards)

            store = SupabaseStrategyStore()
            experiment = store.create_experiment({
                "strategy_name": name,
                "strategy_version": version,
                "instrument": result["instrument"],
                "timeframe": result["timeframe"],
                "days": result["days"],
                "grid": {"risks": risk, "stops": stops, "rewards": rewards, "source": "controlled_auto_research"},
                "validation": result["validation"],
                "results": result["results"],
            })
            _json(self, {
                "mode": "research",
                "live_trading_enabled": False,
                "engine": "controlled_grid",
                "experiment": experiment,
                "validation": result["validation"],
                "count": result["count"],
                "results": result["results"],
            })
        except Exception as exc:
            _json(self, {"error": str(exc), "mode": "research", "live_trading_enabled": False}, 400)
