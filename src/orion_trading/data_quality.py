from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

EXPECTED_MINUTES = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}

@dataclass(frozen=True)
class DataQualityReport:
    rows: int
    duplicate_rows: int
    missing_bars: int
    bad_ohlc: int
    non_utc_index: bool
    passed: bool

def validate_candles(df: pd.DataFrame, timeframe: str) -> DataQualityReport:
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing OHLC columns: {required - set(df.columns)}")
    idx = pd.DatetimeIndex(df.index)
    duplicate_rows = int(idx.duplicated().sum())
    non_utc = idx.tz is None or str(idx.tz) != "UTC"
    bad_ohlc = int(((df["high"] < df[["open","close","low"]].max(axis=1)) |
                    (df["low"] > df[["open","close","high"]].min(axis=1))).sum())
    missing = 0
    if len(idx) > 1:
        delta = idx.to_series().diff().dropna()
        expected = pd.Timedelta(minutes=EXPECTED_MINUTES[timeframe])
        missing = int((delta > expected).sum())
    passed = duplicate_rows == 0 and bad_ohlc == 0 and not non_utc
    return DataQualityReport(len(df), duplicate_rows, missing, bad_ohlc, non_utc, passed)
