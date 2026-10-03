from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from .backtest import BacktestConfig, BacktestResult, Backtester
from .monte_carlo import monte_carlo
from .strategy_experiments import StrategyExperimentResult, StrategyExperimenter
from .trading_engine import TradingEngine, TradingEngineConfig
from .validation import walk_forward_splits


@dataclass(frozen=True)
class ExperimentValidationConfig:
    train_days: int = 180
    test_days: int = 60
    step_days: int = 60
    max_candidates: int = 3
    monte_carlo_simulations: int = 5000
    monte_carlo_seed: int = 42


def _backtester(parameters: dict[str, float], config: BacktestConfig) -> Backtester:
    return Backtester(
        engine=TradingEngine(config=TradingEngineConfig(**parameters)),
        config=config,
    )


def validate_experiment(
    candles: pd.DataFrame,
    experiment: StrategyExperimentResult,
    *,
    start: datetime | str,
    end: datetime | str,
    config: ExperimentValidationConfig | None = None,
) -> dict:
    """Walk-forward validate ranked experiment candidates, then stress OOS trades.

    Candidate selection happens only on each training window. The test windows are
    stitched out-of-sample results, preventing the full-period experiment winner
    from leaking into its own validation set.
    """
    cfg = config or ExperimentValidationConfig()
    if cfg.max_candidates <= 0:
        raise ValueError("max_candidates must be positive")
    candidates = tuple(experiment.variants[: cfg.max_candidates])
    folds = walk_forward_splits(
        start, end, cfg.train_days, cfg.test_days, cfg.step_days
    )

    fold_reports: list[dict] = []
    oos_results: list[tuple[BacktestResult, float]] = []

    for fold_number, (train, test) in enumerate(folds, start=1):
        scored: list[tuple[object, BacktestResult]] = []
        for candidate in candidates:
            result = _backtester(
                candidate.parameters, BacktestConfig(
                    initial_equity=cfg_equity(experiment),
                    risk_per_trade_pct=candidate.parameters.get("risk_per_trade_pct", 0.50),
                )
            ).run(
                candles.loc[(candles.index >= train.start) & (candles.index < train.end)],
                instrument=experiment.instrument,
            )
            scored.append((candidate, result))

        if not scored:
            continue

        best_candidate, best_train = max(
            scored, key=lambda item: StrategyExperimenter.score(item[1])
        )
        test_frame = candles.loc[
            (candles.index >= test.start) & (candles.index < test.end)
        ]
        test_result = _backtester(
            best_candidate.parameters,
            BacktestConfig(
                initial_equity=cfg_equity(experiment),
                risk_per_trade_pct=best_candidate.parameters.get("risk_per_trade_pct", 0.50),
            ),
        ).run(test_frame, instrument=experiment.instrument)
        oos_results.append((test_result, best_candidate.parameters.get("risk_per_trade_pct", 0.50)))
        fold_reports.append(
            {
                "fold": fold_number,
                "train_window": {"start": train.start.isoformat(), "end": train.end.isoformat()},
                "test_window": {"start": test.start.isoformat(), "end": test.end.isoformat()},
                "selected_rank": best_candidate.rank,
                "selected_parameters": best_candidate.parameters,
                "train": {
                    "start": train.start.isoformat(),
                    "end": train.end.isoformat(),
                    "trades": len(best_train.trades),
                    "total_return_pct": best_train.total_return_pct,
                    "max_drawdown_pct": best_train.max_drawdown_pct,
                },
                "oos": {
                    "trades": len(test_result.trades),
                    "wins": test_result.wins,
                    "losses": test_result.losses,
                    "total_return_pct": test_result.total_return_pct,
                    "max_drawdown_pct": test_result.max_drawdown_pct,
                    "win_rate_pct": test_result.win_rate_pct,
                    "profit_factor": (
                        None if test_result.profit_factor == float("inf")
                        else test_result.profit_factor
                    ),
                },
            }
        )

    pnl = []
    for result, risk_pct in oos_results:
        risk_amount = max(cfg_equity(experiment) * risk_pct / 100.0, 1e-9)
        for trade in result.trades:
            pnl.append(trade.pnl / risk_amount)
    mc = monte_carlo(
        pnl,
        simulations=cfg.monte_carlo_simulations,
        seed=cfg.monte_carlo_seed,
    )

    return {
        "method": "experiment_candidate_rolling_walk_forward",
        "candidate_count": len(candidates),
        "fold_count": len(fold_reports),
        "folds": fold_reports,
        "oos_trade_count": len(pnl),
        "monte_carlo": {
            "simulations": mc.simulations,
            "trades": mc.trades,
            "median_net_r": mc.median_net_r,
            "p05_net_r": mc.p05_net_r,
            "p95_net_r": mc.p95_net_r,
            "median_max_drawdown_r": mc.median_max_drawdown_r,
            "p95_max_drawdown_r": mc.p95_max_drawdown_r,
            "p95_max_losing_streak": mc.p95_max_losing_streak,
            "negative_finish_pct": mc.negative_finish_pct,
            "normalization": "each trade pnl / (validation starting equity * selected candidate risk %)",
        },
    }


def cfg_equity(experiment: StrategyExperimentResult) -> float:
    """Use the experiment's common starting equity for validation."""
    if experiment.variants:
        return experiment.variants[0].result.initial_equity
    return 10_000.0
