from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class PerformanceReport:
    trades: int
    net_r: float
    win_rate_pct: float
    profit_factor: float | None
    expectancy_r: float
    max_drawdown_r: float
    best_trade_r: float
    worst_trade_r: float


def performance_report(trades: pd.DataFrame) -> PerformanceReport:
    if trades.empty:
        return PerformanceReport(0, 0.0, 0.0, None, 0.0, 0.0, 0.0, 0.0)
    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    equity = pnl.cumsum()
    dd = equity - equity.cummax()
    pf = float(wins.sum() / abs(losses.sum())) if not losses.empty else None
    return PerformanceReport(
        trades=len(pnl), net_r=float(pnl.sum()), win_rate_pct=float((pnl > 0).mean() * 100),
        profit_factor=pf, expectancy_r=float(pnl.mean()), max_drawdown_r=float(abs(dd.min())),
        best_trade_r=float(pnl.max()), worst_trade_r=float(pnl.min()),
    )


def write_json(report: PerformanceReport, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
