import pandas as pd
import pytest
from orion_trading.binance_client import BinanceClient


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.batches.pop(0))


def _candle(open_ms, close="100"):
    return [
        open_ms,
        "99",
        "101",
        "98",
        close,
        "10",
        open_ms + 899999,
        "1000",
        20,
        "5",
        "500",
        "0",
    ]


def _window(first_open, hours=2):
    start = pd.Timestamp(first_open, unit="ms", tz="UTC")
    return start.to_pydatetime(), (start + pd.Timedelta(hours=hours)).to_pydatetime()


def test_binance_candles_normalize_to_canonical_ohlcv():
    first_open = 1760000000000
    start, _ = _window(first_open)
    end = (pd.Timestamp(first_open, unit="ms", tz="UTC") + pd.Timedelta(minutes=15)).to_pydatetime()
    session = FakeSession(
        [[_candle(first_open), _candle(first_open + 15 * 60 * 1000, "101")]]
    )
    client = BinanceClient(session=session, page_limit=2, retry_count=0)

    frame = client.candles("btcusdt", "M15", start, end)

    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert str(frame.index.tz) == "UTC"
    assert frame["close"].tolist() == [100.0, 101.0]
    assert session.calls[0][1]["symbol"] == "BTCUSDT"
    assert session.calls[0][1]["interval"] == "15m"


def test_binance_paginates_when_page_is_full():
    first_open = 1760000000000
    interval = 15 * 60 * 1000
    start, end = _window(first_open)
    first_batch = [_candle(first_open + i * interval) for i in range(2)]
    second_batch = [_candle(first_open + 2 * interval, "102")]
    session = FakeSession([first_batch, second_batch])
    client = BinanceClient(session=session, page_limit=2, retry_count=0)

    frame = client.candles("BTCUSDT", "M15", start, end)

    assert len(session.calls) == 2
    assert len(frame) == 3
    assert frame["close"].iloc[-1] == 102.0


def test_binance_rejects_unknown_timeframe():
    client = BinanceClient(session=FakeSession([]), retry_count=0)
    with pytest.raises(ValueError, match="Unsupported Binance timeframe"):
        client.candles(
            "BTCUSDT",
            "M5",
            pd.Timestamp("2025-10-09T00:00:00Z").to_pydatetime(),
            pd.Timestamp("2025-10-09T01:00:00Z").to_pydatetime(),
        )
