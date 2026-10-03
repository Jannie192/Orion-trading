from datetime import datetime, timezone

import pandas as pd

from orion_trading.dataset_manager import DatasetManager, find_gaps


def candles(start, count, freq="1h"):
    idx = pd.date_range(start=start, periods=count, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": range(100, 100 + count),
            "high": range(101, 101 + count),
            "low": range(99, 99 + count),
            "close": range(100, 100 + count),
            "volume": [1.0] * count,
        },
        index=idx,
    )


def test_find_gaps_returns_contiguous_missing_ranges():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 6, tzinfo=timezone.utc)
    idx = candles(start, 6).index.delete([2, 3])
    gaps = find_gaps(idx, start, end, "H1")

    assert [(g.start, g.end) for g in gaps] == [
        (
            datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 4, tzinfo=timezone.utc),
        )
    ]


class FakeProvider:
    def __init__(self):
        self.calls = []

    def candles(self, instrument, timeframe, start, end):
        self.calls.append((instrument, timeframe, start, end))
        step = pd.Timedelta(hours=1)
        idx = pd.date_range(start=start, end=end - step, freq=step, tz="UTC")
        return pd.DataFrame(
            {
                "open": [100.0] * len(idx),
                "high": [101.0] * len(idx),
                "low": [99.0] * len(idx),
                "close": [100.0] * len(idx),
                "volume": [1.0] * len(idx),
            },
            index=idx,
        )


class FakeStore:
    def __init__(self, initial):
        self.frame = initial.copy()
        self.records = []

    def load(self, instrument, timeframe, start_at=None, end_at=None, limit=10000):
        result = self.frame.copy()
        if start_at:
            result = result[result.index >= pd.Timestamp(start_at)]
        if end_at:
            result = result[result.index < pd.Timestamp(end_at)]
        return result.iloc[:limit]

    def save(self, instrument, timeframe, frame, provider):
        self.frame = pd.concat([self.frame, frame]).sort_index()
        self.frame = self.frame[~self.frame.index.duplicated(keep="last")]
        return len(frame)

    def record_dataset(self, **kwargs):
        self.records.append(kwargs)


def test_sync_downloads_only_missing_gap_and_records_manifest():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 6, tzinfo=timezone.utc)
    initial = candles(start, 6).drop(candles(start, 6).index[[2, 3]])

    provider = FakeProvider()
    store = FakeStore(initial)
    result = DatasetManager(store, provider, "fake").sync(
        "EURUSD", "H1", start, end
    )

    assert len(provider.calls) == 1
    assert provider.calls[0][2] == datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    assert provider.calls[0][3] == datetime(2026, 1, 1, 4, tzinfo=timezone.utc)
    assert result.existing_rows == 4
    assert result.downloaded_rows == 2
    assert result.gaps_filled == 1
    assert result.final_rows == 6
    assert result.quality_passed is True
    assert len(store.records) == 1
    assert store.records[0]["instrument"] == "EURUSD"


def test_sync_reuses_complete_dataset_without_provider_call():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, 6, tzinfo=timezone.utc)
    provider = FakeProvider()
    store = FakeStore(candles(start, 6))

    result = DatasetManager(store, provider, "fake").sync(
        "EURUSD", "H1", start, end
    )

    assert provider.calls == []
    assert result.gaps_filled == 0
    assert result.downloaded_rows == 0
    assert result.final_rows == 6
