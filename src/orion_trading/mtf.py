from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from .features import calculate_features
from .models import Direction, Regime

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
