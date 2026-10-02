import json
from datetime import datetime, timezone

import pandas as pd

from orion_trading.historical_dataset import build_historical_dataset


class FakeProvider:
    def candles(self, instrument, timeframe, start, end):
        idx = pd.date_range(start=start, periods=3, freq={"M15":"15min","H1":"1h"}[timeframe], tz="UTC")
        base = 100.0 if instrument == "BTCUSDT" else 200.0
        return pd.DataFrame(
            {
                "open": [base, base + 1, base + 2],
                "high": [base + 1, base + 2, base + 3],
                "low": [base - 1, base, base + 1],
                "close": [base + 0.5, base + 1.5, base + 2.5],
                "volume": [10, 11, 12],
            },
            index=idx,
        )


def test_build_historical_dataset_writes_all_artifacts(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    manifest = tmp_path / "manifest.json"

    dataset = build_historical_dataset(
        FakeProvider(),
        "fake",
        ["BTCUSDT", "ETHUSDT"],
        start,
        end,
        timeframes=["H1", "M15"],
        manifest_path=manifest,
    )

    assert len(dataset.artifacts) == 4
    assert all(item.quality_passed for item in dataset.artifacts)
    assert all(len(item.sha256) == 64 for item in dataset.artifacts)

    payload = json.loads(manifest.read_text())
    assert payload["provider"] == "fake"
    assert len(payload["artifacts"]) == 4
    assert (tmp_path / "does-not-exist").exists() is False


def test_historical_dataset_is_reproducible_for_same_input(tmp_path):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)

    first = build_historical_dataset(
        FakeProvider(), "fake", ["BTCUSDT"], start, end,
        timeframes=["H1"], manifest_path=tmp_path / "one.json"
    )
    second = build_historical_dataset(
        FakeProvider(), "fake", ["BTCUSDT"], start, end,
        timeframes=["H1"], manifest_path=tmp_path / "two.json"
    )

    assert first.artifacts[0].sha256 == second.artifacts[0].sha256
