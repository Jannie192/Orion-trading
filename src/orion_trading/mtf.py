from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .features import calculate_features
from .models import Direction, Regime

_GRANULARITY_MINUTES = {"M15": 15, "H1": 60, "H4": 240, "D": 1440}

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
    bullish = bool(r.close > r.ema20 > r.ema50 and r.roc10 > 0)
    bearish = bool(r.close < r.ema20 < r.ema50 and r.roc10 < 0)
    return bullish, bearish

def build_context(frames: dict[str, pd.DataFrame], regime: Regime, direction: Direction) -> MTFContext:
    d1b, d1s = _trend(frames["D"])
    h4b, h4s = _trend(frames["H4"])
    h1b, h1s = _trend(frames["H1"])
    return MTFContext(regime, direction, d1b, d1s, h4b, h4s, h1b, h1s)

def align_completed_frames(frames: dict[str, pd.DataFrame], event_time: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Align each timeframe using only candles fully completed by event_time."""
    event_time = pd.Timestamp(event_time)
    if event_time.tzinfo is None:
        event_time = event_time.tz_localize("UTC")
    else:
        event_time = event_time.tz_convert("UTC")
    result = {}
    for tf, minutes in _GRANULARITY_MINUTES.items():
        frame = frames[tf]
        if frame.empty:
            result[tf] = frame
            continue
        idx = pd.DatetimeIndex(frame.index)
        complete_at = idx + pd.Timedelta(minutes=minutes)
        result[tf] = frame.loc[complete_at <= event_time]
    return result
