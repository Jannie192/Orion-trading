from datetime import datetime, timezone

import pandas as pd

from orion_trading.backtest import BacktestResult
from orion_trading.dataset_manager import SyncResult
from orion_trading.research_cycle import ResearchCycle


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
