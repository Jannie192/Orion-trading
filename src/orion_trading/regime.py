from __future__ import annotations

import pandas as pd

from .features import atr
from .models import Direction, Regime


def classify_regime(df: pd.DataFrame) -> tuple[Regime, Direction]:
    if len(df) < 60:
        return Regime.RANGE, Direction.NEUTRAL
    close = df["close"]
    fast = close.ewm(span=20, adjust=False).mean()
    slow = close.ewm(span=50, adjust=False).mean()
    atr14 = atr(df).iloc[-1]
    if pd.isna(atr14) or atr14 <= 0:
        return Regime.RANGE, Direction.NEUTRAL
    slope = (fast.iloc[-1] - fast.iloc[-10]) / atr14
    if abs(slope) < 0.25:
        return Regime.RANGE, Direction.NEUTRAL
    if fast.iloc[-1] > slow.iloc[-1] and slope > 0:
        return Regime.TREND_UP, Direction.LONG
    if fast.iloc[-1] < slow.iloc[-1] and slope < 0:
        return Regime.TREND_DOWN, Direction.SHORT
    return Regime.TRANSITION, Direction.NEUTRAL
