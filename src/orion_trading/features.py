from __future__ import annotations

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"]-df["low"], (df["high"]-prev).abs(), (df["low"]-prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff()
    up = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50.0)


def roc(df: pd.DataFrame, period: int = 10) -> pd.Series:
    return df["close"].pct_change(periods=period)


def structure_features(df: pd.DataFrame, lookback: int = 20) -> dict[str, float | bool]:
    if len(df) < lookback + 2:
        return {"ready": False}
    recent = df.iloc[-lookback:]
    prior = df.iloc[-lookback-1:-1]
    close = float(df.iloc[-1]["close"])
    high = float(prior["high"].max())
    low = float(prior["low"].min())
    return {"ready": True, "recent_high": float(recent["high"].max()), "recent_low": float(recent["low"].min()), "prior_high": high, "prior_low": low, "close": close, "breakout_up": close > high, "breakout_down": close < low}


def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["atr14"] = atr(out)
    out["rsi14"] = rsi(out)
    out["roc10"] = roc(out)
    out["range"] = out["high"] - out["low"]
    out["range_atr"] = out["range"] / out["atr14"].replace(0, np.nan)
    out["atr_percentile"] = out["atr14"].rolling(100, min_periods=20).rank(pct=True)
    out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
    out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
    return out
