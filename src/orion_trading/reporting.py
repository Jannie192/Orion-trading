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
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()
    pf = float(wins.sum() / abs(losses.sum())) if not losses.empty else None
    return PerformanceReport(
        len(pnl),
        float(pnl.sum()),
        float((pnl > 0).mean() * 100),
        pf,
        float(pnl.mean()),
        float(abs(drawdown.min())),
        float(pnl.max()),
        float(pnl.min()),
    )


def write_backtest_report(
    summary: object, trades: pd.DataFrame, directory: str = "reports"
) -> dict[str, str]:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    sp, tp, ep = out / "summary.json", out / "trades.csv", out / "equity.csv"

    report = summary if hasattr(summary, "__dataclass_fields__") else performance_report(trades)
    sp.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    trades.to_csv(tp, index=False)

    equity = trades[["entry_time", "pnl_r"]].copy() if not trades.empty else pd.DataFrame(
        columns=["entry_time", "pnl_r"]
    )
    if not equity.empty:
        equity["equity_r"] = equity["pnl_r"].cumsum()
        equity["drawdown_r"] = equity["equity_r"] - equity["equity_r"].cummax()
    equity.to_csv(ep, index=False)

    return {"summary": str(sp), "trades": str(tp), "equity": str(ep)}


def write_charts(trades: pd.DataFrame, directory: str = "reports/charts") -> dict[str, str]:
    """Create research charts; requires the optional charting dependency."""
    if trades.empty:
        return {}
    import matplotlib.pyplot as plt

    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)

    pnl = pd.to_numeric(trades["pnl_r"], errors="coerce").dropna()
    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()

    paths = {}
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(equity.to_numpy())
    ax.set_title("ORION Equity Curve")
    ax.set_xlabel("Trade")
    ax.set_ylabel("R")
    fig.tight_layout()
    path = out / "equity_curve.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths["equity_curve"] = str(path)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(range(len(drawdown)), drawdown.to_numpy(), 0)
    ax.set_title("ORION Drawdown")
    ax.set_xlabel("Trade")
    ax.set_ylabel("R")
    fig.tight_layout()
    path = out / "drawdown.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths["drawdown"] = str(path)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(pnl.to_numpy(), bins=min(30, max(5, len(pnl) // 5)))
    ax.set_title("Trade P/L Distribution")
    ax.set_xlabel("P/L (R)")
    ax.set_ylabel("Count")
    fig.tight_layout()
    path = out / "trade_distribution.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    paths["trade_distribution"] = str(path)

    return paths


def write_json(report: PerformanceReport, path: str | Path) -> None:
    Path(path).write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
