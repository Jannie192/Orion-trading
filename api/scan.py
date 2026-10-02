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

from orion_trading.provider_factory import provider_from_env  # noqa: E402
from orion_trading.scanner import MarketScanner  # noqa: E402

DEFAULT_INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
DEFAULT_TIMEFRAMES = ("H4", "H1", "M15")


def _json_candidate(candidate):
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


def scan():
    provider_name = os.getenv("ORION_DATA_PROVIDER", "binance").lower()
    if provider_name != "binance":
        # Scanning is read-only; other providers can be enabled explicitly
        # once their credentials are configured in the deployment.
        provider = provider_from_env()
    else:
        os.environ["ORION_DATA_PROVIDER"] = "binance"
        provider = provider_from_env()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=14)
    scanner = MarketScanner(provider, DEFAULT_TIMEFRAMES)
    try:
        results = scanner.scan(DEFAULT_INSTRUMENTS, start=start, end=end)
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    return {
        "mode": "paper",
        "live_trading_enabled": False,
        "provider": provider_name,
        "scanned_at": end.isoformat(),
        "results": [
            {
                "instrument": r.instrument,
                "timeframe": r.timeframe,
                "scanned_at": r.scanned_at.isoformat(),
                "regime": r.regime,
                "direction": r.direction,
                "candidates": [_json_candidate(c) for c in r.candidates],
            }
            for r in results
        ],
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            payload = json.dumps(scan(), separators=(",", ":")).encode("utf-8")
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
