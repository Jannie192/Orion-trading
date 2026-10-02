from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from orion_trading.provider_factory import provider_from_env
from orion_trading.backtest import Backtester, BacktestConfig

_ALLOWED = {"BTCUSDT", "ETHUSDT", "EURUSD", "GBPUSD", "NAS100", "US30"}
_TFS = {"M15", "H1", "H4", "D1"}

def run(instrument: str, timeframe: str, days: int):
    if instrument not in _ALLOWED or timeframe not in _TFS:
        raise ValueError("UNSUPPORTED_BACKTEST_REQUEST")
    days = max(7, min(days, 365))
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    os.environ.setdefault("ORION_DATA_PROVIDER", "binance")
    provider = provider_from_env()
    try:
        candles = provider.candles(instrument, timeframe, start, end)
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()
    result = Backtester(config=BacktestConfig(initial_equity=10000.0, risk_per_trade_pct=0.50)).run(
        candles, instrument=instrument
    )
    payload = result.__dict__.copy()
    payload["trades"] = [t.__dict__ for t in result.trades]
    payload["direction"] = [t.direction.value for t in result.trades]
    payload["timeframe"] = timeframe
    payload["days"] = days
    payload["mode"] = "research"
    payload["live_trading_enabled"] = False
    payload["trades_count"] = len(result.trades)
    payload.pop("trades", None)
    payload["trade_log"] = [t.__dict__ | {"direction": t.direction.value, "entry_time": t.entry_time.isoformat(), "exit_time": t.exit_time.isoformat()} for t in result.trades]
    payload["equity_curve"] = []
    equity = float(result.initial_equity)
    for trade in result.trades:
        equity += float(trade.pnl)
        payload["equity_curve"].append({"time": trade.exit_time.isoformat(), "equity": equity})
    result, replay = Backtester(config=BacktestConfig(initial_equity=10000.0, risk_per_trade_pct=0.50)).run_replay(
        candles, instrument=instrument
    )
    payload = {
        "initial_equity": result.initial_equity,
        "final_equity": result.final_equity,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": result.win_rate_pct,
        "profit_factor": None if result.profit_factor == float("inf") else result.profit_factor,
        "timeframe": timeframe,
        "days": days,
        "mode": "research",
        "live_trading_enabled": False,
        "trades_count": len(result.trades),
        "trade_log": [t.__dict__ | {"direction": t.direction.value, "entry_time": t.entry_time.isoformat(), "exit_time": t.exit_time.isoformat()} for t in result.trades],
        "equity_curve": [],
        "replay": replay,
        "replay_bars": len(replay),
    }
    equity = float(result.initial_equity)
    for trade in result.trades:
        equity += float(trade.pnl)
        payload["equity_curve"].append({"time": trade.exit_time.isoformat(), "equity": equity})
    return payload

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            q = parse_qs(urlparse(self.path).query)
            instrument = q.get("instrument", ["BTCUSDT"])[0].upper()
            timeframe = q.get("timeframe", ["H1"])[0].upper()
            days = int(q.get("days", ["90"])[0])
            payload = json.dumps(run(instrument, timeframe, days), default=str, separators=(",", ":")).encode()
            status = 200
        except Exception as exc:
            payload = json.dumps({"mode":"research","live_trading_enabled":False,"error":str(exc)}, separators=(",", ":")).encode()
            status = 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
