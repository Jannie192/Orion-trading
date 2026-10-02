from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
            raise ValueError(
                f"Data quality failed for {instrument}/{timeframe}: "
                f"{report}"
            )
        path = store.save(instrument, timeframe, frame)
        results.append(IngestionResult(
            instrument, timeframe, len(frame), str(path),
            report.passed, report.missing_bars
        ))
    return results
