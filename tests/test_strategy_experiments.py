import pandas as pd
import pytest
from datetime import datetime, timezone

from orion_trading.backtest import BacktestResult, BacktestTrade
from orion_trading.models import Direction
from orion_trading.strategy_experiments import (
    StrategyExperimentResult,
    StrategyExperimenter,
    serialise_experiment,
)


def _result(return_pct=10.0, drawdown=5.0, trades=20):
    return BacktestResult(
        initial_equity=10_000,
        final_equity=10_000 * (1 + return_pct / 100),
        total_return_pct=return_pct,
        max_drawdown_pct=drawdown,
        trades=(BacktestTrade("TEST", Direction.LONG, datetime.now(timezone.utc), datetime.now(timezone.utc), 1, 2, 1, return_pct, "TARGET"),) * trades,
        wins=trades,
        losses=0,
        win_rate_pct=100.0 if trades else 0.0,
        profit_factor=float("inf") if trades else 0.0,
    )


def test_score_rewards_return_relative_to_drawdown_and_sample_size():
    full = StrategyExperimenter.score(_result(10, 5, 20))
    half = StrategyExperimenter.score(_result(10, 5, 10))
    assert full == 2.0
    assert half == 1.0


def test_grid_validation_and_variant_limit():
    experimenter = StrategyExperimenter(max_variants=2)
    candles = pd.DataFrame()
    with pytest.raises(ValueError, match="max_variants"):
        experimenter.run(
            candles,
            instrument="EURUSD",
            timeframe="H1",
            parameter_grid={
                "atr_stop_multiple": [1.0, 1.5],
                "reward_multiple": [1.5, 2.0],
            },
        )


def test_empty_data_still_evaluates_each_variant_deterministically():
    experimenter = StrategyExperimenter(max_variants=4)
    result = experimenter.run(
        pd.DataFrame(),
        instrument="EURUSD",
        timeframe="H1",
        parameter_grid={"atr_stop_multiple": [1.0, 1.5]},
    )
    assert isinstance(result, StrategyExperimentResult)
    assert result.variant_count == 2
    assert result.best is None
    assert all(v.rank == 1 or v.rank == 2 for v in result.variants)


def test_serialise_experiment_is_json_compatible():
    experiment = StrategyExperimentResult(
        strategy_name="ORION",
        strategy_version="experiment",
        instrument="EURUSD",
        timeframe="H1",
        variants=(),
        best=None,
    )
    payload = serialise_experiment(experiment)
    assert payload["variant_count"] == 0
    assert payload["best"] is None
