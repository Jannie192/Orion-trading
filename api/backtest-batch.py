from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from orion_trading.provider_factory import provider_from_env
from orion_trading.backtest import Backtester, BacktestConfig
from orion_trading.trading_engine import TradingEngine, TradingEngineConfig

_ALLOWED = {"BTCUSDT", "ETHUSDT"}
_TFS = {"M15", "H1", "H4", "D1"}

def _floats(value: str, *, minimum: float, maximum: float) -> list[float]:
    out = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        x = float(raw)
        if minimum <= x <= maximum:
            out.append(x)
    if not out:
        raise ValueError("EMPTY_PARAMETER_GRID")
    return list(dict.fromkeys(out))

def run(instrument: str, timeframe: str, days: int, risks: str, stops: str, rewards: str):
    if instrument not in _ALLOWED or timeframe not in _TFS:
        raise ValueError("BATCH_PROVIDER_CURRENTLY_SUPPORTS_CRYPTO_ONLY")
    days = max(7, min(days, 365))
    risk_values = _floats(risks, minimum=0.05, maximum=2.0)
    stop_values = _floats(stops, minimum=0.5, maximum=4.0)
    reward_values = _floats(rewards, minimum=0.5, maximum=6.0)
    combinations = len(risk_values) * len(stop_values) * len(reward_values)
    if combinations > 100:
        raise ValueError("EXPERIMENT_GRID_TOO_LARGE_MAX_100_RUNS")

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

    results = []
    for risk in risk_values:
        for stop in stop_values:
            for reward in reward_values:
                engine = TradingEngine(config=TradingEngineConfig(
                    risk_per_trade_pct=risk,
                    atr_stop_multiple=stop,
                    reward_multiple=reward,
                ))
                result = Backtester(
                    engine=engine,
                    config=BacktestConfig(initial_equity=10000.0, risk_per_trade_pct=risk),
                ).run(candles, instrument=instrument)
                pf = result.profit_factor
                results.append({
                    "risk_per_trade_pct": risk,
                    "atr_stop_multiple": stop,
                    "reward_multiple": reward,
                    "initial_equity": result.initial_equity,
                    "final_equity": result.final_equity,
                    "total_return_pct": result.total_return_pct,
                    "max_drawdown_pct": result.max_drawdown_pct,
                    "trades_count": len(result.trades),
                    "wins": result.wins,
                    "losses": result.losses,
                    "win_rate_pct": result.win_rate_pct,
                    "profit_factor": None if pf == float("inf") else pf,
                })
    return {
        "mode": "research",
        "live_trading_enabled": False,
        "instrument": instrument,
        "timeframe": timeframe,
        "days": days,
        "count": len(results),
        "results": results,
    }
