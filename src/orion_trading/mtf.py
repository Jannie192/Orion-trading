from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .features import calculate_features
from .models import Direction, Regime

_TIMEFRAME_KEYS = {"D1": "D", "D": "D", "H4": "H4", "H1": "H1", "M15": "M15"}

@dataclass(frozen=True)
class MTFContext:
    regime: Regime
    direction: Direction
    d1_bullish: bool
    d1_bearish: bool
    h4_bullish: bool
    h4_bearish: bool
    h1_bullish: bool
    h1_bearish: bool

def _trend(df: pd.DataFrame) -> tuple[bool, bool]:
    x = calculate_features(df).dropna()
    if x.empty:
        return False, False
    r = x.iloc[-1]
    return bool(r.close > r.ema20 > r.ema50 and r.roc10 > 0), bool(r.close < r.ema20 < r.ema50 and r.roc10 < 0)

def build_context(frames: dict[str, pd.DataFrame], regime: Regime, direction: Direction) -> MTFContext:
    d1 = frames.get("D", frames.get("D1", pd.DataFrame()))
    d1b, d1s = _trend(d1)
    h4b, h4s = _trend(frames["H4"])
    h1b, h1s = _trend(frames["H1"])
    return MTFContext(regime, direction, d1b, d1s, h4b, h4s, h1b, h1s)

def align_completed_frames(frames: dict[str, pd.DataFrame], event_time: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Use only candles whose next observed candle begins by event_time."""
    event_time = pd.Timestamp(event_time)
    event_time = event_time.tz_localize("UTC") if event_time.tzinfo is None else event_time.tz_convert("UTC")
    result = {}
    for supplied_tf, frame in frames.items():
        key = _TIMEFRAME_KEYS.get(supplied_tf, supplied_tf)
        if frame.empty:
            result[key] = frame
            continue
        idx = pd.DatetimeIndex(frame.index)
        if len(idx) < 2:
            result[key] = frame.iloc[0:0]
            continue
        next_start = pd.Series(idx, index=idx).shift(-1)
        mask = next_start.notna() & (next_start <= event_time)
        result[key] = frame.loc[mask.to_numpy()]
    return result
