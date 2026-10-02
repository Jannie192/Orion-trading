import pandas as pd

from orion_trading.research_runner import research_frame, run_research


def _frame(seed: float):
    idx = pd.date_range("2026-01-01", periods=70, freq="h", tz="UTC")
    close = pd.Series(seed + range(70).__iter__().__next__() if False else [seed + i for i in range(70)], index=idx)
    return pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": 100.0,
        },
        index=idx,
    )


def test_research_runner_reports_missing_markets_without_substitution():
    run = run_research(
        {"BTCUSDT": _frame(100), "ETHUSDT": _frame(200)},
        instruments=("BTCUSDT", "ETHUSDT", "EURUSD"),
    )

    assert run.available == ("BTCUSDT", "ETHUSDT")
    assert run.missing == ("EURUSD",)
    assert len(run.backtest.markets) == 2

    frame = research_frame(run)
    assert list(frame["instrument"]) == ["BTCUSDT", "ETHUSDT"]
