from __future__ import annotations

from dataclasses import dataclass, asdict
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
class IngestionResult:
    instrument: str
    timeframe: str
    rows: int
    path: str
    passed: bool
    missing_bars: int
    sha256: str = ""


def _frame_hash(frame: pd.DataFrame) -> str:
    normalized = frame.sort_index().copy()
    normalized.index = pd.DatetimeIndex(normalized.index).tz_convert("UTC")
    payload = normalized.to_csv(
        index=True,
        date_format="%Y-%m-%dT%H:%M:%S.%f%z",
        float_format="%.12g",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def ingest(
    provider: MarketDataAdapter,
    instrument: str,
    start: datetime,
    end: datetime,
    store: CsvDataStore | None = None,
) -> list[IngestionResult]:
    store = store or CsvDataStore()
    results: list[IngestionResult] = []
    for timeframe in TIMEFRAMES:
        frame = provider.candles(instrument, timeframe, start, end)
        if not frame.empty:
            frame = frame.sort_index()
            frame = frame[~frame.index.duplicated(keep="last")]
            if frame.index.tz is None:
                frame.index = frame.index.tz_localize("UTC")
            else:
                frame.index = frame.index.tz_convert("UTC")
        report = validate_candles(frame, timeframe) if not frame.empty else None
        if report is None or not report.passed:
            raise ValueError(f"Data quality failed for {instrument}/{timeframe}: {report}")
        path = store.save(instrument, timeframe, frame)
        results.append(IngestionResult(
            instrument, timeframe, len(frame), str(path), report.passed,
            report.missing_bars, _frame_hash(frame)
        ))
    return results


def write_manifest(
    results: Iterable[IngestionResult],
    provider: str,
    manifest_path: str | Path = "data/market/manifest.json",
) -> Path:
    """Write a reproducible dataset manifest with UTC creation time and content hashes."""
    target = Path(manifest_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "provider": provider,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": [asdict(result) for result in results],
    }
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def ingest_with_manifest(
    provider: MarketDataAdapter,
    provider_name: str,
    instrument: str,
    start: datetime,
    end: datetime,
    store: CsvDataStore | None = None,
    manifest_path: str | Path = "data/market/manifest.json",
) -> list[IngestionResult]:
    """Ingest all standard timeframes and persist a reproducible dataset manifest."""
    results = ingest(provider, instrument, start, end, store=store)
    write_manifest(results, provider_name, manifest_path)
    return results
