import pandas as pd
import numpy as np

from orion_trading.backtest_engine import SimpleOAFSBacktester, BacktestConfig

def test_backtest_returns_expected_schema():
    n = 180
    close = np.linspace(1.0, 1.2, n)
    frame = pd.DataFrame({
        "open": close,
        "high": close + 0.002,
        "low": close - 0.002,
        "close": close,
        "volume": 1000,
    })
    summary, trades = SimpleOAFSBacktester(BacktestConfig()).run(frame)
    assert summary.trades >= 0
    assert "pnl_r" in trades.columns or trades.empty
