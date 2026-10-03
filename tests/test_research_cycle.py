from datetime import datetime, timezone

from orion_trading.backtest import BacktestResult
from orion_trading.dataset_manager import SyncResult
from orion_trading.research_cycle import ResearchCycle, ResearchResult


class FakeStore:
    pass


class FakeManager:
    store = FakeStore()

    def sync(self, instrument, timeframe, start, end):
        return SyncResult(
            instrument, timeframe, start, end, 100, 4, 1, 104, True
        )


class FakeBacktester:
    def __init__(self):
        self.calls = []

    def run_from_store(self, store, **kwargs):
        self.calls.append((store, kwargs))
        return BacktestResult(10000, 10200, 2.0, 1.0, (), 0, 0, 0.0, 0.0)


class FakeResultStore:
    def __init__(self):
        self.calls = []

    def record_research_result(self, **kwargs):
        self.calls.append(kwargs)
        return "run-123"


def test_research_cycle_syncs_data_then_backtests_from_store():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    backtester = FakeBacktester()

    results = ResearchCycle(FakeManager(), backtester).run(
        ["EURUSD"], ["H1"], start, end
    )

    assert len(results) == 1
    assert results[0].data_rows == 104
    assert results[0].data_downloaded == 4
    assert results[0].gaps_filled == 1
    assert results[0].backtest.final_equity == 10200
    assert backtester.calls[0][0] is FakeManager.store
    assert backtester.calls[0][1]["start_at"].endswith("+00:00")
    assert backtester.calls[0][1]["end_at"].endswith("+00:00")


def test_research_cycle_persists_result_and_returns_run_id():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)
    result_store = FakeResultStore()

    results = ResearchCycle(
        FakeManager(),
        FakeBacktester(),
        result_store=result_store,
        strategy_name="ORION",
        strategy_version="1.0",
    ).run(["EURUSD"], ["H1"], start, end)

    assert results[0].run_id == "run-123"
    assert len(result_store.calls) == 1
    assert result_store.calls[0]["strategy_name"] == "ORION"
    assert result_store.calls[0]["strategy_version"] == "1.0"
    assert isinstance(result_store.calls[0]["result"], ResearchResult)
    assert result_store.calls[0]["start_at"].endswith("+00:00")


class FakeExperimenter:
    def __init__(self):
        self.calls = []

    def run(self, candles, **kwargs):
        self.calls.append((candles, kwargs))
        from orion_trading.strategy_experiments import StrategyExperimentResult
        return StrategyExperimentResult(
            strategy_name=kwargs["strategy_name"],
            strategy_version=kwargs["strategy_version"],
            instrument=kwargs["instrument"],
            timeframe=kwargs["timeframe"],
            variants=(),
            best=None,
        )


class FakeExperimentStore:
    def __init__(self):
        self.calls = []

    def record_strategy_experiment(self, **kwargs):
        self.calls.append(kwargs)
        return "experiment-123"


def test_research_cycle_runs_and_persists_experiments_when_configured():
    import pandas as pd

    class Store(FakeStore):
        def load(self, *args, **kwargs):
            return pd.DataFrame(
                {"open": [], "high": [], "low": [], "close": [], "volume": []},
                index=pd.DatetimeIndex([], tz="UTC"),
            )

    manager = FakeManager()
    manager.store = Store()
    experimenter = FakeExperimenter()
    experiment_store = FakeExperimentStore()

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 2, 1, tzinfo=timezone.utc)

    ResearchCycle(
        manager,
        FakeBacktester(),
        experimenter=experimenter,
        experiment_store=experiment_store,
        experiment_grids={"*": {"atr_stop_multiple": [1.0, 1.5]}},
    ).run(["EURUSD"], ["H1"], start, end)

    assert len(experimenter.calls) == 1
    assert experimenter.calls[0][1]["instrument"] == "EURUSD"
    assert experimenter.calls[0][1]["timeframe"] == "H1"
    assert experimenter.calls[0][1]["parameter_grid"]["atr_stop_multiple"] == [1.0, 1.5]
    assert len(experiment_store.calls) == 1
    assert experiment_store.calls[0]["experiment"].instrument == "EURUSD"
    assert "validation" in experiment_store.calls[0]
    assert experiment_store.calls[0]["validation"]["method"] == "experiment_candidate_rolling_walk_forward"
