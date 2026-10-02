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
from orion_trading.signal_scoring import score_candidate
from orion_trading.portfolio_risk import PortfolioPosition, PortfolioRiskGate
from orion_trading.models import Direction
from orion_trading.trade_planner import plan_trade
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
        scan_results = scanner.scan(INSTRUMENTS, start=start, end=end)
        for result in scan_results:
            results.append({
                "instrument": result.instrument,
                "timeframe": result.timeframe,
                "scanned_at": result.scanned_at.isoformat(),
                "regime": result.regime,
                "direction": result.direction,
                "candidates": [],
            })
            bucket = results[-1]["candidates"]
            # Re-fetch the timeframe candles so valid signals receive concrete
            # entry/stop/target levels before the paper-order safety gate.
            candles = provider.candles(result.instrument, result.timeframe, start, end)
            for candidate in result.candidates:
                planned = plan_trade(candidate, candles)
                scored = score_candidate(planned, timeframe=result.timeframe, aligned_timeframes=tuple(
                    r.timeframe for r in scan_results
                    if r.instrument == result.instrument
                    and r.timeframe != result.timeframe
                    and any(x.valid and x.direction == planned.direction for x in r.candidates)
                ))
                item = _candidate(planned)
                item["score"] = scored.score
                item["confidence"] = scored.confidence
                item["confirmations"] = list(scored.confirmations)
                item["penalties"] = list(scored.penalties)
                bucket.append(item)
                if planned.valid:
                    decisions.append({
                        "timeframe": result.timeframe,
                        "candidate": planned,
                    })
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    service = PaperSignalService(store)
    gate = PortfolioRiskGate()
    snapshot = store.snapshot()
    existing_positions = [
        PortfolioPosition(
            instrument=p["instrument"],
            direction=Direction(p["direction"].upper()),
            notional=float(p.get("entry", 0)) * float(p.get("units", 0)),
            risk_amount=abs(float(p.get("entry", 0)) - float(p.get("stop", 0))) * float(p.get("units", 0)),
        )
        for p in snapshot.get("open_positions", [])
    ]
    equity = float(snapshot.get("account", {}).get("equity", 0) or 0)
    persisted = []
    for item in decisions:
        candidate = item["candidate"]
        proposed_risk_pct = 0.5
        portfolio = gate.approve(
            equity=equity,
            proposed_instrument=candidate.instrument,
            proposed_direction=candidate.direction,
            proposed_risk_pct=proposed_risk_pct,
            positions=existing_positions,
        )
        if not portfolio.approved:
            persisted.append({
                "instrument": candidate.instrument,
                "timeframe": item["timeframe"],
                "order_id": None,
                "accepted": False,
                "reason": portfolio.reason,
            })
            continue
        decision = service.submit(candidate, item["timeframe"])
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
