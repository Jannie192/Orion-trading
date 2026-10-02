from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .costs import ExecutionCostConfig, apply_cost
from .features import calculate_features


@dataclass(frozen=True)
class BacktestConfig:
    risk_r: float = 1.0
    atr_stop_multiple: float = 1.5
    reward_multiple: float = 2.0
    costs: ExecutionCostConfig = ExecutionCostConfig()


@dataclass(frozen=True)
class BacktestSummary:
    trades: int
    wins: int
    losses: int
    net_r: float
    win_rate_pct: float
    profit_factor: float | None
    expectancy_r: float
    max_drawdown_r: float


class SimpleOAFSBacktester:
    """Deterministic research harness, not the final OAFS implementation."""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(self, candles: pd.DataFrame) -> tuple[BacktestSummary, pd.DataFrame]:
        x = calculate_features(candles).dropna().copy()
        rows = []
        for i in range(1, len(x)):
            c, p = x.iloc[i], x.iloc[i - 1]
            long = bool(c.close > c.ema20 > c.ema50 and c.roc10 > 0 and p.close <= p.ema20)
            short = bool(c.close < c.ema20 < c.ema50 and c.roc10 < 0 and p.close >= p.ema20)
            if not (long or short):
                continue

            direction = 1 if long else -1
            entry = float(c.close)
            stop_distance = float(c.atr14) * self.config.atr_stop_multiple
            if stop_distance <= 0:
                continue

            stop = entry - direction * stop_distance
            target = entry + direction * stop_distance * self.config.reward_multiple
            pnl = 0.0
            reason = "DATA_END"
            exit_i = len(x) - 1

            for j in range(i + 1, len(x)):
                b = x.iloc[j]
                if direction == 1 and b.low <= stop:
                    pnl = -self.config.risk_r
                    reason = "STOP"
                    exit_i = j
                    break
                if direction == 1 and b.high >= target:
                    pnl = self.config.reward_multiple * self.config.risk_r
                    reason = "TARGET"
                    exit_i = j
                    break
                if direction == -1 and b.high >= stop:
                    pnl = -self.config.risk_r
                    reason = "STOP"
                    exit_i = j
                    break
                if direction == -1 and b.low <= target:
                    pnl = self.config.reward_multiple * self.config.risk_r
                    reason = "TARGET"
                    exit_i = j
                    break

            gross_pnl = pnl if reason != "DATA_END" else direction * (float(x.iloc[exit_i].close) - entry) / stop_distance
            net_pnl = apply_cost(gross_pnl, entry, stop_distance, self.config.costs)
            rows.append({
                "entry_time": x.index[i],
                "exit_time": x.index[exit_i],
                "direction": "LONG" if direction == 1 else "SHORT",
                "entry": entry,
                "stop": stop,
                "target": target,
                "gross_pnl_r": float(gross_pnl),
                "pnl_r": float(net_pnl),
                "cost_r": float(gross_pnl - net_pnl),
                "exit_reason": reason,
            })

        trades = pd.DataFrame(rows)
        if trades.empty:
            return BacktestSummary(0, 0, 0, 0.0, 0.0, None, 0.0, 0.0), trades

        pnl = trades.pnl_r.astype(float)
        wins, losses = pnl[pnl > 0], pnl[pnl < 0]
        equity = pnl.cumsum()
        drawdown = equity - equity.cummax()
        profit_factor = float(wins.sum() / abs(losses.sum())) if not losses.empty else None
        return BacktestSummary(
            len(pnl),
            len(wins),
            len(losses),
            float(pnl.sum()),
            float((pnl > 0).mean() * 100),
            profit_factor,
            float(pnl.mean()),
            float(abs(drawdown.min())),
        ), trades
