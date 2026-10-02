from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.paper_signal_service import PaperSignalService
from orion_trading.provider_factory import provider_from_env
from orion_trading.scanner import MarketScanner
from orion_trading.supabase_paper_store import SupabasePaperStore

INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("H4", "H1", "M15")


def _candidate(candidate):
    return {
        "instrument": candidate.instrument,
        "detected_at": candidate.detected_at.isoformat(),
        "regime": candidate.regime.value,
        "direction": candidate.direction.value,
        "opportunities": [x.value for x in candidate.opportunities],
        "evidence": candidate.evidence,
        "entry": candidate.entry,
        "stop": candidate.stop,
        "target": candidate.target,
        "valid": candidate.valid,
        "rejection_reason": candidate.rejection_reason,
    }


def scan_and_persist():
    store = SupabasePaperStore()
    provider_name = os.getenv("ORION_DATA_PROVIDER", "binance").lower()
    if provider_name == "binance":
        os.environ["ORION_DATA_PROVIDER"] = "binance"
    provider = provider_from_env()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=14)
    scanner = MarketScanner(provider, TIMEFRAMES)
    decisions = []
    results = []
    try:
        for result in scanner.scan(INSTRUMENTS, start=start, end=end):
            results.append({
                "instrument": result.instrument,
                "timeframe": result.timeframe,
                "scanned_at": result.scanned_at.isoformat(),
                "regime": result.regime,
                "direction": result.direction,
                "candidates": [],
            })
            bucket = results[-1]["candidates"]
            for candidate in result.candidates:
                bucket.append(_candidate(candidate))
                if candidate.valid:
                    decisions.append({
                        "timeframe": result.timeframe,
                        "candidate": candidate,
                    })
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    service = PaperSignalService(store)
    persisted = []
    for item in decisions:
        decision = service.submit(item["candidate"], item["timeframe"])
        persisted.append({
            "instrument": item["candidate"].instrument,
            "timeframe": item["timeframe"],
            "order_id": decision.order_id,
            "accepted": decision.accepted,
            "reason": decision.reason,
        })

    return {
        "mode": "paper",
        "live_trading_enabled": False,
        "provider": provider_name,
        "scanned_at": end.isoformat(),
        "results": results,
        "paper_orders": persisted,
        "paper_state": store.snapshot(),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = json.dumps(scan_and_persist(), separators=(",", ":")).encode("utf-8")
            status = 200
        except Exception as exc:
            payload = json.dumps({
                "mode": "paper",
                "live_trading_enabled": False,
                "error": str(exc),
                "results": [],
            }, separators=(",", ":")).encode("utf-8")
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
