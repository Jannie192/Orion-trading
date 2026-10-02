from datetime import datetime, timezone
import pandas as pd

from orion_trading.scanner import MarketScanner


class FakeProvider:
    def __init__(self, frame):
        self.frame = frame
        self.calls = []

    def candles(self, instrument, timeframe, start, end):
        self.calls.append((instrument, timeframe))
        return self.frame.copy()


def candles(n=100):
    idx = pd.date_range("2026-01-01", periods=n, freq="h", tz="UTC")
    close = pd.Series(range(100, 100 + n), index=idx, dtype=float)
    return pd.DataFrame({
        "open": close - 0.2, "high": close + 0.5,
        "low": close - 0.5, "close": close, "volume": 1000.0
    }, index=idx)


def test_scanner_covers_all_instruments_and_timeframes():
    provider = FakeProvider(candles())
    scanner = MarketScanner(provider, ("H1", "M15"))
    results = scanner.scan(
        ["EUR_USD", "BTC_USDT"],
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert len(results) == 4
    assert len(provider.calls) == 4


def test_actionable_only_returns_valid_candidates():
    provider = FakeProvider(candles())
    scanner = MarketScanner(provider, ("H1",))
    results = scanner.scan(
        ["EUR_USD"],
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert all(candidate.valid for candidate in scanner.actionable(results))
