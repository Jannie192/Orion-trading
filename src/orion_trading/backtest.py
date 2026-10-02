from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Iterable
import pandas as pd
from .models import Direction
from .trading_engine import TradingEngine, TradingEngineConfig

# Research-grade wrapper retained for compatibility with the existing engine.

@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    risk_per_trade_pct: float = 0.50
    commission_per_unit: float = 0.0
    slippage_per_unit: float = 0.0

@dataclass(frozen=True)
class BacktestTrade:
    instrument: str
    direction: Direction
    entry_time: datetime
    exit_time: datetime
    entry: float
    exit: float
    units: float
    pnl: float
    reason: str

@dataclass(frozen=True)
class BacktestResult:
    initial_equity: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trades: tuple[BacktestTrade, ...]
    wins: int
    losses: int
    win_rate_pct: float
    profit_factor: float

class Backtester:
    """Bar-by-bar backtester with next-bar fills and conservative intrabar ordering."""

    def __init__(self, engine: TradingEngine | None = None, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()
        self.engine = engine or TradingEngine(
            config=TradingEngineConfig(risk_per_trade_pct=self.config.risk_per_trade_pct)
        )

    def run(self, candles: pd.DataFrame, *, instrument: str) -> BacktestResult:
        if candles.empty or len(candles) < 61:
            return self._result(self.config.initial_equity, ())
        frame = candles.sort_index()
        equity = self.config.initial_equity
        peak = equity
        max_dd = 0.0
        trades: list[BacktestTrade] = []
        i = 60
        while i < len(frame) - 1:
            evaluation = self.engine.evaluate(frame.iloc[:i + 1], instrument=instrument, equity=equity)
            plan = next((p for p in evaluation.plans if p.risk.approved and p.candidate.valid), None)
            if plan is None:
                i += 1
                continue
            entry_i = i + 1
            entry = float(frame.iloc[entry_i]["open"])
            distance = abs(plan.entry - plan.stop)
            direction = plan.candidate.direction
            stop = entry - distance if direction is Direction.LONG else entry + distance
            target = entry + distance * self.engine.config.reward_multiple if direction is Direction.LONG else entry - distance * self.engine.config.reward_multiple
            units = plan.position.units
            exit_i, exit_price, reason = len(frame) - 1, float(frame.iloc[-1]["close"]), "END_OF_DATA"
            for j in range(entry_i, len(frame)):
                high, low = float(frame.iloc[j]["high"]), float(frame.iloc[j]["low"])
                stop_hit = low <= stop if direction is Direction.LONG else high >= stop
                target_hit = high >= target if direction is Direction.LONG else low <= target
                if stop_hit:
                    exit_i, exit_price, reason = j, stop, "STOP"
                    break
                if target_hit:
                    exit_i, exit_price, reason = j, target, "TARGET"
                    break
            gross = (exit_price - entry) * units if direction is Direction.LONG else (entry - exit_price) * units
            pnl = gross - units * (self.config.commission_per_unit + self.config.slippage_per_unit)
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
            trades.append(BacktestTrade(instrument, direction, frame.index[entry_i].to_pydatetime(), frame.index[exit_i].to_pydatetime(), entry, exit_price, units, pnl, reason))
            i = exit_i + 1
        return self._result(equity, trades, max_dd)

    def _result(self, final_equity: float, trades: Iterable[BacktestTrade], max_dd: float = 0.0) -> BacktestResult:
        trades = tuple(trades)
        wins = sum(t.pnl > 0 for t in trades)
        losses = sum(t.pnl < 0 for t in trades)
        gp = sum(t.pnl for t in trades if t.pnl > 0)
        gl = -sum(t.pnl for t in trades if t.pnl < 0)
        pf = gp / gl if gl else (math.inf if gp else 0.0)
        return BacktestResult(self.config.initial_equity, final_equity, (final_equity / self.config.initial_equity - 1) * 100, max_dd * 100, trades, wins, losses, wins / len(trades) * 100 if trades else 0.0, pf)
