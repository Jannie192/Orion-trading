from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable
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
    progress: Callable[[int, int, str], None] | None = None,
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
    selected_ranks: list[int] = []

    total_folds = len(folds)
    if progress is not None:
        progress(0, total_folds, "start")
    for fold_number, (train, test) in enumerate(folds, start=1):
        if progress is not None:
            progress(fold_number, total_folds, "start")
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
        selected_ranks.append(best_candidate.rank)
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
        if progress is not None:
            progress(fold_number, total_folds, "complete")

    pnl = []
    oos_wins = 0
    oos_losses = 0
    for result, risk_pct in oos_results:
        oos_wins += result.wins
        oos_losses += result.losses
        risk_amount = max(cfg_equity(experiment) * risk_pct / 100.0, 1e-9)
        for trade in result.trades:
            pnl.append(trade.pnl / risk_amount)

    oos_trade_count = oos_wins + oos_losses
    oos_win_rate_pct = (
        oos_wins / oos_trade_count * 100.0 if oos_trade_count else 0.0
    )

    mc = monte_carlo(
        pnl,
        simulations=cfg.monte_carlo_simulations,
        seed=cfg.monte_carlo_seed,
    )
    mc_payload = {
        "median_net_r": mc.median_net_r,
        "p05_net_r": mc.p05_net_r,
        "p95_max_drawdown_r": mc.p95_max_drawdown_r,
        "p95_max_losing_streak": mc.p95_max_losing_streak,
        "negative_finish_pct": mc.negative_finish_pct,
    }
    approval = approve_validation(
        {
            "fold_count": len(fold_reports),
            "oos_trade_count": oos_trade_count,
            "oos_win_rate_pct": oos_win_rate_pct,
            "monte_carlo": mc_payload,
        }
    )

    validated_candidate = None
    if selected_ranks and candidates:
        selected_rank = max(
            sorted(set(selected_ranks)),
            key=lambda rank: (selected_ranks.count(rank), -rank),
        )
        selected = next((candidate for candidate in candidates if candidate.rank == selected_rank), None)
        if selected is not None:
            validated_candidate = {
                "rank": selected.rank,
                "parameters": selected.parameters,
                "selection_count": selected_ranks.count(selected.rank),
                "selection_rate_pct": selected_ranks.count(selected.rank) / len(selected_ranks) * 100.0,
            }

    return {
        "method": "experiment_candidate_rolling_walk_forward",
        "candidate_count": len(candidates),
        "fold_count": len(fold_reports),
        "folds": fold_reports,
        "oos_trade_count": oos_trade_count,
        "oos_wins": oos_wins,
        "oos_losses": oos_losses,
        "oos_win_rate_pct": oos_win_rate_pct,
        "validated_candidate": validated_candidate,
        "approval": approval,
        "monte_carlo": {
            "simulations": mc.simulations,
            "trades": mc.trades,
            "median_net_r": mc.median_net_r,
            "p05_net_r": mc.p05_net_r,
            "p95_max_drawdown_r": mc.p95_max_drawdown_r,
            "p95_max_losing_streak": mc.p95_max_losing_streak,
            "negative_finish_pct": mc.negative_finish_pct,
            "normalization": "each trade pnl / (validation starting equity * selected candidate risk %)",
        },
    }


@dataclass(frozen=True)
class CandidateApprovalConfig:
    min_folds: int = 3
    min_oos_trades: int = 30
    min_oos_win_rate_pct: float = 75.0
    min_median_net_r: float = 0.0
    min_p05_net_r: float = 0.0
    max_negative_finish_pct: float = 45.0
    max_p95_drawdown_r: float = 12.0
    max_p95_losing_streak: int = 10


def approve_validation(validation: dict, *, config: CandidateApprovalConfig | None = None) -> dict:
    """Apply deterministic quantitative gates before paper-trading admission."""
    cfg = config or CandidateApprovalConfig()
    mc = validation.get("monte_carlo") or {}
    checks = {
        "minimum_folds": validation.get("fold_count", 0) >= cfg.min_folds,
        "minimum_oos_trades": validation.get("oos_trade_count", 0) >= cfg.min_oos_trades,
        "minimum_oos_win_rate": validation.get("oos_win_rate_pct", 0.0) >= cfg.min_oos_win_rate_pct,
        "median_net_r_non_negative": mc.get("median_net_r", 0.0) >= cfg.min_median_net_r,
        "p05_net_r_non_negative": mc.get("p05_net_r", 0.0) >= cfg.min_p05_net_r,
        "negative_finish_within_limit": mc.get("negative_finish_pct", 100.0) <= cfg.max_negative_finish_pct,
        "p95_drawdown_within_limit": mc.get("p95_max_drawdown_r", float("inf")) <= cfg.max_p95_drawdown_r,
        "p95_losing_streak_within_limit": mc.get("p95_max_losing_streak", 10**9) <= cfg.max_p95_losing_streak,
    }
    passed = all(checks.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "thresholds": {
            "min_folds": cfg.min_folds,
            "min_oos_trades": cfg.min_oos_trades,
            "min_oos_win_rate_pct": cfg.min_oos_win_rate_pct,
            "min_median_net_r": cfg.min_median_net_r,
            "min_p05_net_r": cfg.min_p05_net_r,
            "max_negative_finish_pct": cfg.max_negative_finish_pct,
            "max_p95_drawdown_r": cfg.max_p95_drawdown_r,
            "max_p95_losing_streak": cfg.max_p95_losing_streak,
        },
        "next_stage": "PAPER_TRADING_CANDIDATE" if passed else "RESEARCH",
    }


def cfg_equity(experiment: StrategyExperimentResult) -> float:
    """Use the experiment's common starting equity for validation."""
    if experiment.variants:
        return experiment.variants[0].result.initial_equity
    return 10_000.0
