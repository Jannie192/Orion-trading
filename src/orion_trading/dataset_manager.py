from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import pandas as pd

from .data_quality import validate_candles
from .historical_dataset import _frame_hash
from .market_data import MarketDataAdapter


class MarketDataStore(Protocol):
    def load(self, instrument: str, timeframe: str, start_at: str | None = None, end_at: str | None = None, limit: int = 10000, provider: str | None = None) -> pd.DataFrame: ...
    def save(self, instrument: str, timeframe: str, frame: pd.DataFrame, provider: str) -> int: ...
    def record_dataset(self, **kwargs) -> None: ...


@dataclass(frozen=True)
class DataGap:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class SyncResult:
    instrument: str
    timeframe: str
    requested_start: datetime
    requested_end: datetime
    existing_rows: int
    downloaded_rows: int
    gaps_filled: int
    final_rows: int
    quality_passed: bool


_EXPECTED_MINUTES = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    idx = pd.DatetimeIndex(result.index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    result.index = idx
    return result.sort_index()[~result.index.duplicated(keep="last")]


def _is_expected_market_timestamp(ts: pd.Timestamp) -> bool:
    # Spot FX is normally closed over Saturday/Sunday. Do not treat those
    # calendar periods as missing candles.
    return ts.weekday() < 5


def find_gaps(index: pd.DatetimeIndex, start: datetime, end: datetime, timeframe: str) -> list[DataGap]:
    timeframe = timeframe.upper()
    if timeframe not in _EXPECTED_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    start, end = _utc(start), _utc(end)
    step = timedelta(minutes=_EXPECTED_MINUTES[timeframe])
    expected = pd.date_range(start=start, end=end - step, freq=step)
    expected = expected[expected.map(_is_expected_market_timestamp)]

    existing = pd.DatetimeIndex(index)
    existing = existing.tz_localize("UTC") if existing.tz is None else existing.tz_convert("UTC")
    existing = existing[(existing >= start) & (existing < end)]
    present = set(existing)

    gaps: list[DataGap] = []
    gap_start: datetime | None = None
    for ts in expected:
        ts_dt = ts.to_pydatetime()
        if ts not in present:
            if gap_start is None:
                gap_start = ts_dt
        elif gap_start is not None:
            gaps.append(DataGap(gap_start, ts_dt))
            gap_start = None
    if gap_start is not None:
        gaps.append(DataGap(gap_start, end))
    return gaps


class DatasetManager:
    """Keeps persistent market data complete for requested time ranges."""

    def __init__(self, store: MarketDataStore, provider: MarketDataAdapter, provider_name: str, *, fetch_limit: int = 10000) -> None:
        if fetch_limit <= 0:
            raise ValueError("fetch_limit must be positive")
        self.store = store
        self.provider = provider
        self.provider_name = provider_name
        self.fetch_limit = fetch_limit

    def sync(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> SyncResult:
        start, end = _utc(start), _utc(end)
        if start >= end:
            raise ValueError("start must be earlier than end")
        timeframe = timeframe.upper()

        existing = _normalise(self.store.load(
            instrument, timeframe, start_at=start.isoformat(), end_at=end.isoformat(),
            limit=self.fetch_limit, provider=self.provider_name,
        ))
        gaps = find_gaps(existing.index, start, end, timeframe)
        downloaded = 0

        for gap in gaps:
            frame = _normalise(self.provider.candles(instrument, timeframe, gap.start, gap.end))
            if frame.empty:
                raise ValueError(
                    f"Provider returned no data for {instrument}/{timeframe} gap {gap.start.isoformat()} to {gap.end.isoformat()}"
                )
            report = validate_candles(frame, timeframe)
            if not report.passed:
                raise ValueError(f"Data quality failed for {instrument}/{timeframe}: {report}")
            downloaded += self.store.save(instrument, timeframe, frame, self.provider_name)

        final = _normalise(self.store.load(
            instrument, timeframe, start_at=start.isoformat(), end_at=end.isoformat(),
            limit=self.fetch_limit, provider=self.provider_name,
        ))
        final_report = validate_candles(final, timeframe) if not final.empty else None
        if final_report is None or not final_report.passed:
            raise ValueError(f"Final data quality failed for {instrument}/{timeframe}: {final_report}")

        self.store.record_dataset(
            provider=self.provider_name, instrument=instrument, timeframe=timeframe,
            start_at=start.isoformat(), end_at=end.isoformat(), row_count=len(final),
            missing_bars=final_report.missing_bars, sha256=_frame_hash(final),
            quality_passed=final_report.passed, artifact_path=None,
        )

        return SyncResult(
            instrument=instrument, timeframe=timeframe, requested_start=start,
            requested_end=end, existing_rows=len(existing), downloaded_rows=downloaded,
            gaps_filled=len(gaps), final_rows=len(final), quality_passed=final_report.passed,
        )
