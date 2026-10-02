from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

from .data_quality import validate_candles
from .data_store import CsvDataStore
from .market_data import MarketDataAdapter

TIMEFRAMES = ("D1", "H4", "H1", "M15")


@dataclass(frozen=True)
class DatasetArtifact:
    instrument: str
    timeframe: str
    rows: int
    start: str
    end: str
    path: str
    sha256: str
    missing_bars: int
    quality_passed: bool


@dataclass(frozen=True)
class HistoricalDataset:
    provider: str
    created_at: str
    artifacts: tuple[DatasetArtifact, ...]

    def write_manifest(self, path: str | Path = "data/market/manifest.json") -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "provider": self.provider,
            "created_at": self.created_at,
            "artifacts": [asdict(item) for item in self.artifacts],
        }
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return target


def _frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.sort_index().copy()
    idx = pd.DatetimeIndex(normalized.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    normalized.index = idx
    payload = normalized.to_csv(
        index=True,
        date_format="%Y-%m-%dT%H:%M:%S.%f%z",
        float_format="%.12g",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.sort_index().copy()
    idx = pd.DatetimeIndex(result.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    result.index = idx
    return result[~result.index.duplicated(keep="last")]


def build_historical_dataset(
    provider: MarketDataAdapter,
    provider_name: str,
    instruments: Iterable[str],
    start: datetime,
    end: datetime,
    store: CsvDataStore | None = None,
    timeframes: Iterable[str] = TIMEFRAMES,
    manifest_path: str | Path = "data/market/manifest.json",
) -> HistoricalDataset:
    if start >= end:
        raise ValueError("start must be earlier than end")

    store = store or CsvDataStore()
    artifacts: list[DatasetArtifact] = []

    for instrument in instruments:
        for timeframe in timeframes:
            timeframe = timeframe.upper()
            frame = _normalise(provider.candles(instrument, timeframe, start, end))
            if frame.empty:
                raise ValueError(f"No historical data returned for {instrument}/{timeframe}")

            report = validate_candles(frame, timeframe)
            if not report.passed:
                raise ValueError(
                    f"Data quality failed for {instrument}/{timeframe}: {report}"
                )

            path = store.save(instrument, timeframe, frame)
            artifacts.append(
                DatasetArtifact(
                    instrument=instrument,
                    timeframe=timeframe,
                    rows=len(frame),
                    start=frame.index.min().isoformat(),
                    end=frame.index.max().isoformat(),
                    path=str(path),
                    sha256=_frame_hash(frame),
                    missing_bars=report.missing_bars,
                    quality_passed=report.passed,
                )
            )

    dataset = HistoricalDataset(
        provider=provider_name,
        created_at=datetime.now(timezone.utc).isoformat(),
        artifacts=tuple(artifacts),
    )
    dataset.write_manifest(manifest_path)
    return dataset
