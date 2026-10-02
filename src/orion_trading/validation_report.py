from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from .monte_carlo import monte_carlo
from .portfolio_backtest import combine_trade_logs, summarize_portfolio
from .regime_analysis import summarize_by_regime
from .validation import equity_stats, walk_forward_splits
from .equity import equity_frame, write_equity_charts

def _utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")

def _setup_analysis(trades: list[dict]) -> dict:
    if not trades:
        return {}
    df = pd.DataFrame(trades)
    if "pnl_r" not in df or "opportunities" not in df:
        return {}
    df["pnl_r"] = pd.to_numeric(df["pnl_r"], errors="coerce").fillna(0.0)
    out = {}
    for name, group in df.explode("opportunities").groupby("opportunities", dropna=False):
        pnl = group["pnl_r"]
        gross_loss = -pnl[pnl < 0].sum()
        out[str(name)] = {
            "trades": int(len(group)),
            "net_r": float(pnl.sum()),
            "win_rate_pct": float((pnl > 0).mean() * 100),
            "expectancy_r": float(pnl.mean()),
            "profit_factor": float(pnl[pnl > 0].sum() / gross_loss) if gross_loss else None,
        }
    return out

def _rejection_analysis(results: list[dict]) -> dict:
    reasons = [
        str(rejection.get("reason", "UNKNOWN"))
        for result in results
        for rejection in result.get("rejections", [])
    ]
    if not reasons:
        return {}
    counts = pd.Series(reasons).value_counts()
    return {str(k): int(v) for k, v in counts.items()}

def build_validation_report(
    results: list[dict],
    start,
    end,
    *,
    data_quality: dict | None = None,
    train_days: int = 180,
    test_days: int = 60,
    step_days: int = 60,
    simulations: int = 10000,
    walk_forward: dict | None = None,
) -> dict:
    trades_df = combine_trade_logs(results)
    trades = trades_df.to_dict("records") if not trades_df.empty else []
    portfolio = summarize_portfolio(results)
    pnl = trades_df["pnl_r"].astype(float).tolist() if not trades_df.empty else []
    splits = walk_forward_splits(_utc(start), _utc(end), train_days, test_days, step_days)

    wf = walk_forward
    if wf is None:
        wf = {
            "method": "rolling_windows",
            "train_days": train_days,
            "test_days": test_days,
            "step_days": step_days,
            "folds": [
                {
                    "train": {"name": a.name, "start": a.start.isoformat(), "end": a.end.isoformat()},
                    "test": {"name": b.name, "start": b.start.isoformat(), "end": b.end.isoformat()},
                }
                for a, b in splits
            ],
            "performance_evaluated": False,
            "note": "Fold metadata only; this report does not claim fold-level out-of-sample performance.",
        }

    oos_results = wf.get("oos_results", []) if isinstance(wf, dict) else []
    oos_trades_df = combine_trade_logs(oos_results) if oos_results else pd.DataFrame()
    oos_pnl = oos_trades_df["pnl_r"].astype(float).tolist() if not oos_trades_df.empty else []
    mc_pnl = oos_pnl if oos_pnl else pnl
    mc = monte_carlo(mc_pnl, simulations=simulations) if mc_pnl else None

    return {
        "schema_version": "1.0",
        "strategy": "OAFS",
        "strategy_version": "1.0.0",
        "status": "research_only",
        "live_trading_enabled": False,
        "period": {"start": _utc(start).isoformat(), "end": _utc(end).isoformat()},
        "portfolio": {
            "trades": portfolio.trades,
            "wins": portfolio.wins,
            "losses": portfolio.losses,
            "net_r": portfolio.net_r,
            "win_rate_pct": portfolio.win_rate_pct,
            "profit_factor": None if portfolio.profit_factor == float("inf") else portfolio.profit_factor,
            "expectancy_r": portfolio.expectancy_r,
            "max_drawdown_r": portfolio.max_drawdown_r,
        },
        "equity": equity_stats(pnl),
        "pairs": {
            str(r.get("instrument")): {k: v for k, v in r.items() if k not in {"trade_log", "rejections"}}
            for r in results
        },
        "regimes": summarize_by_regime(trades),
        "opportunity_types": _setup_analysis(trades),
        "rejections": _rejection_analysis(results),
        "walk_forward": wf,
        "monte_carlo": None if mc is None else {
            "simulations": mc.simulations,
            "trades": mc.trades,
            "median_net_r": mc.median_net_r,
            "p05_net_r": mc.p05_net_r,
            "p95_net_r": mc.p95_net_r,
            "median_max_drawdown_r": mc.median_max_drawdown_r,
            "p95_max_drawdown_r": mc.p95_max_drawdown_r,
            "p95_max_losing_streak": mc.p95_max_losing_streak,
            "negative_finish_pct": mc.negative_finish_pct,
            "method": "iid_bootstrap_with_replacement",
            "source": "walk_forward_oos" if oos_pnl else "full_sample_backtest",
            "warning": "Stress simulation of observed trade outcomes, not proof of future performance.",
        },
        "data_quality": data_quality or {},
        "_trades": trades,
        "_rejections": [dict(x, instrument=r.get("instrument")) for r in results for x in r.get("rejections", [])],
    }
def write_validation_report(report: dict, directory="reports/validation") -> Path:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(report, indent=2, default=str))
    pairs = report.get("pairs", {})
    pd.DataFrame(pairs.values()).assign(instrument=list(pairs.keys())).to_csv(out / "pairs.csv", index=False)

    trades = []
    for pair in pairs.values():
        trades.extend(pair.get("trade_log", []))
    # Pair summaries intentionally omit trade logs; recover the combined log from the report inputs
    # when this writer is called with the optional embedded trade data.
    if report.get("_trades"):
        trades = report["_trades"]
    if trades:
        trade_df = pd.DataFrame(trades)
        trade_df.to_csv(out / "trades.csv", index=False)
        equity_frame(trades).to_csv(out / "equity.csv", index=False)
        write_equity_charts(trades, out / "charts")

    rejections = report.get("_rejections", [])
    if rejections:
        pd.DataFrame(rejections).to_csv(out / "rejections.csv", index=False)

    # Internal report payloads are useful for artifact generation but should not leak into summary.json.
    summary = dict(report)
    summary.pop("_trades", None)
    summary.pop("_rejections", None)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    return out / "summary.json"
