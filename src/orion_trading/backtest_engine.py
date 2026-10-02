from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .features import calculate_features


@dataclass(frozen=True)
class BacktestConfig:
    risk_r: float = 1.0
    atr_stop_multiple: float = 1.5
    reward_multiple: float = 2.0


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
    """Deterministic research harness; intentionally not a live execution engine."""

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(self, candles: pd.DataFrame) -> tuple[BacktestSummary, pd.DataFrame]:
        x = calculate_features(candles).dropna().copy()
        rows = []
        for i in range(1, len(x)):
            cur = x.iloc[i]
            prev = x.iloc[i - 1]
            long_setup = cur.close > cur.ema20 > cur.ema50 and cur.roc10 > 0 and prev.close <= prev.ema20
            short_setup = cur.close < cur.ema20 < cur.ema50 and cur.roc10 < 0 and prev.close >= prev.ema20
            if not (long_setup or short_setup):
                continue
            entry = float(cur.close)
            atr = float(cur.atr14)
            stop_dist = atr * self.config.atr_stop_multiple
            if stop_dist <= 0:
                continue
            direction = 1 if long_setup else -1
            stop = entry - direction * stop_dist
            target = entry + direction * stop_dist * self.config.reward_multiple
            pnl_r = 0.0
            exit_reason = "DATA_END"
            for j in range(i + 1, len(x)):
                bar = x.iloc[j]
                if direction == 1:
                    if bar.low <= stop:
                        pnl_r = -self.config.risk_r; exit_reason = "STOP"; exit_i = j; break
                    if bar.high >= target:
                        pnl_r = self.config.reward_multiple * self.config.risk_r; exit_reason = "TARGET"; exit_i = j; break
                else:
                    if bar.high >= stop:
                        pnl_r = -self.config.risk_r; exit_reason = "STOP"; exit_i = j; break
                    if bar.low <= target:
                        pnl_r = self.config.reward_multiple * self.config.risk_r; exit_reason = "TARGET"; exit_i = j; break
            else:
                exit_i = len(x) - 1
                final = float(x.iloc[exit_i].close)
                pnl_r = direction * (final - entry) / stop_dist
            rows.append({"entry_time": x.index[i], "exit_time": x.index[exit_i], "direction": "LONG" if direction == 1 else "SHORT", "entry": entry, "stop": stop, "target": target, "pnl_r": float(pnl_r), "exit_reason": exit_reason})
        trades = pd.DataFrame(rows)
        if trades.empty:
            return BacktestSummary(0, 0, 0, 0.0, 0.0, None, 0.0, 0.0), trades
        pnl = trades.pnl_r.astype(float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
        equity = pnl.cumsum()
        dd = equity - equity.cummax()
        pf = float(wins.sum() / abs(losses.sum())) if not losses.empty else None
        return BacktestSummary(len(pnl), len(wins), len(losses), float(pnl.sum()), float((pnl > 0).mean()*100), pf, float(pnl.mean()), float(abs(dd.min()))), trades
