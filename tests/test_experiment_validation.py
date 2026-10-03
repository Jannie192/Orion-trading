import pandas as pd

from orion_trading.backtest import BacktestResult
from orion_trading.experiment_validation import ExperimentValidationConfig, validate_experiment
from orion_trading.strategy_experiments import StrategyExperimentResult, StrategyVariant


def _result(pnl: float) -> BacktestResult:
    return BacktestResult(
        initial_equity=10_000.0,
        final_equity=10_000.0 + pnl,
        total_return_pct=pnl / 100.0,
        max_drawdown_pct=1.0,
        trades=(),
        wins=0,
        losses=0,
        win_rate_pct=0.0,
        profit_factor=0.0,
    )


class FakeBacktester:
    pass


def test_validation_returns_walk_forward_and_monte_carlo(monkeypatch):
    import orion_trading.experiment_validation as module

    calls = []

    class FakeRunner:
        def __init__(self, result):
            self.result = result

        def run(self, candles, *, instrument):
            calls.append((len(candles), instrument))
            return self.result

    results = [_result(100.0), _result(50.0)]

    def fake_backtester(parameters, config):
        return FakeRunner(results[len(calls) % 2])

    monkeypatch.setattr(module, "_backtester", fake_backtester)

    candles = pd.DataFrame(
        {
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 1.0,
        },
        index=pd.date_range("2026-01-01", periods=300, freq="D", tz="UTC"),
    )
    variant = StrategyVariant({"risk_per_trade_pct": 0.5, "atr_stop_multiple": 1.5, "reward_multiple": 2.0}, _result(100), 10.0, 1)
    experiment = StrategyExperimentResult("ORION", "1.0-experiment", "EURUSD", "D1", (variant,), variant)

    result = validate_experiment(
        candles,
        experiment,
        start="2026-01-01",
        end="2026-10-01",
        config=ExperimentValidationConfig(
            train_days=30, test_days=10, step_days=10, monte_carlo_simulations=100
        ),
    )

    assert result["method"] == "experiment_candidate_rolling_walk_forward"
    assert result["fold_count"] > 0
    assert result["monte_carlo"]["simulations"] == 100
    assert calls
