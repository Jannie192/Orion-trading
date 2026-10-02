from __future__ import annotations

from dataclasses import replace

import pandas as pd

from .models import Direction, SignalCandidate


def plan_trade(
    candidate: SignalCandidate,
    candles: pd.DataFrame,
    *,
    atr_stop_multiple: float = 1.5,
    reward_multiple: float = 2.0,
) -> SignalCandidate:
    """Attach deterministic ATR-based entry/stop/target levels to a valid signal.

    This is planning only: it never submits an order or enables live execution.
    """
    if not candidate.valid or candidate.direction is Direction.NEUTRAL:
        return candidate
    if candles.empty:
        return replace(candidate, valid=False, rejection_reason="INSUFFICIENT_DATA")

    from .features import calculate_features

    features = calculate_features(candles).dropna()
    if features.empty:
        return replace(candidate, valid=False, rejection_reason="INSUFFICIENT_FEATURES")

    last = features.iloc[-1]
    entry = float(last["close"])
    atr = float(last["atr14"])
    if not pd.notna(atr) or atr <= 0:
        return replace(candidate, valid=False, rejection_reason="INVALID_ATR")

    distance = atr * atr_stop_multiple
    if candidate.direction is Direction.LONG:
        stop = entry - distance
        target = entry + distance * reward_multiple
    else:
        stop = entry + distance
        target = entry - distance * reward_multiple

    evidence = dict(candidate.evidence)
    evidence.update({
        "entry_model": "ATR",
        "atr14": atr,
        "atr_stop_multiple": atr_stop_multiple,
        "reward_multiple": reward_multiple,
        "risk_reward": reward_multiple,
    })
    return replace(candidate, entry=entry, stop=stop, target=target, evidence=evidence)
