import pandas as pd

from orion_trading.multi_market_backtest import run_multi_market_backtest, results_frame


def _candles():
    idx = pd.date_range("2026-01-01", periods=70, freq="h", tz="UTC")
    close = pd.Series(range(100, 170), index=idx, dtype=float)
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


def test_multi_market_runs_same_rules_for_each_market():
    result = run_multi_market_backtest({"BTCUSDT": _candles(), "ETHUSDT": _candles()})

    assert len(result.markets) == 2
    assert {item.instrument for item in result.markets} == {"BTCUSDT", "ETHUSDT"}
    assert all(item.result.initial_equity == 10_000.0 for item in result.markets)

    frame = results_frame(result)
    assert list(frame["instrument"]) == ["BTCUSDT", "ETHUSDT"]
    assert {"trades", "return_pct", "max_drawdown_pct"}.issubset(frame.columns)


def test_multi_market_does_not_claim_shared_capital():
    result = run_multi_market_backtest({"BTCUSDT": _candles()})
    assert result.initial_equity_per_market == 10_000.0
