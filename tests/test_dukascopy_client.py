import pandas as pd

import orion_trading.dukascopy_client as client


def test_dukascopy_symbol_resolution(monkeypatch):
    class FakeDukas:
        OFFER_SIDE_BID = "bid"
        INTERVAL_MIN_15 = "m15"
        INSTRUMENT_EUR_USD = "EUR/USD"

        @staticmethod
        def fetch(instrument, interval, side, start, end):
            assert instrument == "EUR/USD"
            assert interval == "m15"
            assert side == "bid"
            return pd.DataFrame(
                {
                    "timestamp": ["2026-01-01T00:00:00Z"],
                    "open": [1.1],
                    "high": [1.2],
                    "low": [1.0],
                    "close": [1.15],
                    "volume": [10],
                }
            )

    monkeypatch.setattr(client, "dukas", FakeDukas)
    result = client.DukascopyClient().candles(
        "EUR_USD",
        "M15",
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-01-02", tz="UTC"),
    )
    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert result.index[0] == pd.Timestamp("2026-01-01", tz="UTC")
