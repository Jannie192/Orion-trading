import pandas as pd
from .models import Direction, Regime

def classify_regime(df: pd.DataFrame) -> tuple[Regime, Direction]:
    if len(df) < 60 or "atr_14" not in df:
        return Regime.RANGE, Direction.NEUTRAL
    close = df["close"]
    fast = close.ewm(span=20, adjust=False).mean()
    slow = close.ewm(span=50, adjust=False).mean()
    atr = df["atr_14"].iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return Regime.RANGE, Direction.NEUTRAL
    slope = (fast.iloc[-1] - fast.iloc[-10]) / atr
    if abs(slope) < 0.25:
        return Regime.RANGE, Direction.NEUTRAL
    if fast.iloc[-1] > slow.iloc[-1] and slope > 0:
        return Regime.TREND_UP, Direction.LONG
    if fast.iloc[-1] < slow.iloc[-1] and slope < 0:
        return Regime.TREND_DOWN, Direction.SHORT
    return Regime.TRANSITION, Direction.NEUTRAL
