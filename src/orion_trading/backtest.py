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

    def run_from_store(
        self,
        store,
        *,
        instrument: str,
        timeframe: str,
        start_at: str | None = None,
        end_at: str | None = None,
        limit: int = 10000,
    ) -> BacktestResult:
        """Backtest exclusively from candles persisted in a market-data store."""
        candles = store.load(
            instrument,
            timeframe,
            start_at=start_at,
            end_at=end_at,
            limit=limit,
        )
        return self.run(candles, instrument=instrument)

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

    def run_replay(self, candles: pd.DataFrame, *, instrument: str) -> tuple[BacktestResult, list[dict]]:
        """Run the same causal simulation while emitting one event for every candle."""
        if candles.empty or len(candles) < 61:
            return self._result(self.config.initial_equity, ()), []
        frame = candles.sort_index()
        equity = self.config.initial_equity
        peak = equity
        max_dd = 0.0
        trades: list[BacktestTrade] = []
        events: list[dict] = []
        pending = None
        position = None
        trade_index = 0

        for i, (ts, row) in enumerate(frame.iterrows()):
            action = "WAIT"
            signal_direction = None
            regime = None
            opportunities = []
            entry = stop = target = None
            units = 0.0
            realized_pnl = 0.0
            position_status = "FLAT"

            if pending is not None and i == pending["entry_i"]:
                entry = float(row["open"])
                direction = pending["direction"]
                distance = pending["distance"]
                stop = entry - distance if direction is Direction.LONG else entry + distance
                target = entry + distance * self.engine.config.reward_multiple if direction is Direction.LONG else entry - distance * self.engine.config.reward_multiple
                position = {"direction": direction, "entry": entry, "stop": stop, "target": target, "units": pending["units"], "entry_time": ts.to_pydatetime()}
                pending = None
                action = "ENTER"
                position_status = "OPEN"

            if position is not None:
                direction = position["direction"]
                entry = position["entry"]
                stop = position["stop"]
                target = position["target"]
                units = position["units"]
                position_status = "OPEN"
                high, low = float(row["high"]), float(row["low"])
                stop_hit = low <= stop if direction is Direction.LONG else high >= stop
                target_hit = high >= target if direction is Direction.LONG else low <= target
                if stop_hit or target_hit:
                    exit_price = stop if stop_hit else target
                    reason = "STOP" if stop_hit else "TARGET"
                    gross = (exit_price - entry) * units if direction is Direction.LONG else (entry - exit_price) * units
                    pnl = gross - units * (self.config.commission_per_unit + self.config.slippage_per_unit)
                    equity += pnl
                    realized_pnl = pnl
                    peak = max(peak, equity)
                    max_dd = max(max_dd, (peak - equity) / peak if peak else 0.0)
                    trades.append(BacktestTrade(instrument, direction, position["entry_time"], ts.to_pydatetime(), entry, exit_price, units, pnl, reason))
                    trade_index += 1
                    action = "EXIT"
                    position_status = "FLAT"
                    position = None

            if position is None and pending is None and i >= 60 and i < len(frame) - 1:
                evaluation = self.engine.evaluate(frame.iloc[:i + 1], instrument=instrument, equity=equity)
                plan = next((p for p in evaluation.plans if p.risk.approved and p.candidate.valid), None)
                if plan is not None:
                    pending = {"entry_i": i + 1, "direction": plan.candidate.direction, "distance": abs(plan.entry - plan.stop), "units": plan.position.units}
                    signal_direction = plan.candidate.direction.value
                    regime = plan.candidate.regime.value
                    opportunities = [o.value for o in plan.candidate.opportunities]
                    entry, stop, target = plan.entry, plan.stop, plan.target
                    action = "SIGNAL" if action == "WAIT" else action
                    position_status = "PENDING"
                else:
                    signal_direction = None

            unrealized = 0.0
            if position is not None:
                mark = float(row["close"])
                unrealized = (mark - position["entry"]) * position["units"] if position["direction"] is Direction.LONG else (position["entry"] - mark) * position["units"]

            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100 if peak else 0.0
            events.append({
                "time": ts.to_pydatetime().isoformat(),
                "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]), "close": float(row["close"]),
                "volume": float(row["volume"]) if "volume" in row else 0.0,
                "equity": equity, "drawdown_pct": dd, "unrealized_pnl": unrealized, "realized_pnl": realized_pnl,
                "action": action, "trade_index": trade_index, "position_status": position_status,
                "direction": signal_direction or (position["direction"].value if position else None),
                "regime": regime, "opportunities": opportunities, "entry": entry, "stop": stop, "target": target,
                "units": units,
                "trade": ({"direction": trades[-1].direction.value, "entry": trades[-1].entry, "exit": trades[-1].exit, "pnl": trades[-1].pnl, "reason": trades[-1].reason} if action == "EXIT" and trades else None),
            })

        return self._result(equity, trades, max_dd), events

    def _result(self, final_equity: float, trades: Iterable[BacktestTrade], max_dd: float = 0.0) -> BacktestResult:
        trades = tuple(trades)
        wins = sum(t.pnl > 0 for t in trades)
        losses = sum(t.pnl < 0 for t in trades)
        gp = sum(t.pnl for t in trades if t.pnl > 0)
        gl = -sum(t.pnl for t in trades if t.pnl < 0)
        pf = gp / gl if gl else (math.inf if gp else 0.0)
        return BacktestResult(self.config.initial_equity, final_equity, (final_equity / self.config.initial_equity - 1) * 100, max_dd * 100, trades, wins, losses, wins / len(trades) * 100 if trades else 0.0, pf)
