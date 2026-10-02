from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .backtest_oafs import OAFSBacktestConfig, run_oafs_backtest
from .portfolio_backtest import summarize_portfolio
from .validation import walk_forward_splits

@dataclass(frozen=True)
class WalkForwardConfig:
    train_days: int = 180
    test_days: int = 60
    step_days: int = 60
    candidates: tuple[OAFSBacktestConfig, ...] = (
        OAFSBacktestConfig(reward_multiple=1.5, atr_stop_multiple=1.25),
        OAFSBacktestConfig(reward_multiple=2.0, atr_stop_multiple=1.5),
        OAFSBacktestConfig(reward_multiple=2.5, atr_stop_multiple=1.75),
    )

def _score(result: dict) -> tuple[float, float, float]:
    trades = int(result.get("trades", 0))
    expectancy = float(result.get("expectancy_r", 0.0))
    drawdown = float(result.get("max_drawdown_r", 0.0))
    if trades < 5:
        return (-1e9, expectancy, -drawdown)
    return (float(result.get("net_r", 0.0)), expectancy, -drawdown)

def run_walk_forward(frames_by_instrument: dict[str, dict], instruments: list[str],
                     start, end, config: WalkForwardConfig | None = None) -> dict:
    cfg = config or WalkForwardConfig()
    folds = walk_forward_splits(start, end, cfg.train_days, cfg.test_days, cfg.step_days)
    fold_reports = []
    oos_results = []

    for fold_number, (train, test) in enumerate(folds, start=1):
        selected = {}
        train_results = {}

        for instrument in instruments:
            frames = frames_by_instrument[instrument]
            candidates = []
            for candidate in cfg.candidates:
                result = run_oafs_backtest(frames, instrument, candidate, train.start, train.end)
                candidates.append((candidate, result))
            best_config, best_result = max(candidates, key=lambda item: _score(item[1]))
            selected[instrument] = best_config
            train_results[instrument] = {
                "trades": best_result["trades"],
                "net_r": best_result["net_r"],
                "expectancy_r": best_result["expectancy_r"],
                "max_drawdown_r": best_result["max_drawdown_r"],
            }

        test_results = []
        for instrument in instruments:
            result = run_oafs_backtest(
                frames_by_instrument[instrument],
                instrument,
                selected[instrument],
                test.start,
                test.end,
            )
            test_results.append(result)
            oos_results.append(result)

        portfolio = summarize_portfolio(test_results)
        fold_reports.append({
            "fold": fold_number,
            "train": {"start": train.start.isoformat(), "end": train.end.isoformat()},
            "test": {"start": test.start.isoformat(), "end": test.end.isoformat()},
            "selected_configs": {
                instrument: {
                    "risk_fraction": selected[instrument].risk_fraction,
                    "reward_multiple": selected[instrument].reward_multiple,
                    "atr_stop_multiple": selected[instrument].atr_stop_multiple,
                }
                for instrument in instruments
            },
            "train_results": train_results,
            "oos_portfolio": {
                "trades": portfolio.trades,
                "wins": portfolio.wins,
                "losses": portfolio.losses,
                "net_r": portfolio.net_r,
                "win_rate_pct": portfolio.win_rate_pct,
                "profit_factor": None if portfolio.profit_factor == float("inf") else portfolio.profit_factor,
                "expectancy_r": portfolio.expectancy_r,
                "max_drawdown_r": portfolio.max_drawdown_r,
            },
        })

    stitched = summarize_portfolio(oos_results)
    return {
        "method": "rolling_walk_forward",
        "train_days": cfg.train_days,
        "test_days": cfg.test_days,
        "step_days": cfg.step_days,
        "folds": fold_reports,
        "oos_portfolio": {
            "trades": stitched.trades,
            "wins": stitched.wins,
            "losses": stitched.losses,
            "net_r": stitched.net_r,
            "win_rate_pct": stitched.win_rate_pct,
            "profit_factor": None if stitched.profit_factor == float("inf") else stitched.profit_factor,
            "expectancy_r": stitched.expectancy_r,
            "max_drawdown_r": stitched.max_drawdown_r,
        },
        "oos_results": oos_results,
    }
