from __future__ import annotations

from typing import Any

import pandas as pd

from .features import calculate_features, structure_features
from .models import Direction, Opportunity, Regime, SignalCandidate


def _candidate(df: pd.DataFrame, direction: Direction, opportunities: tuple[Opportunity, ...], regime: Regime, evidence: dict[str, Any], valid: bool, reason: str | None = None) -> SignalCandidate:
    ts = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else pd.Timestamp.utcnow().to_pydatetime()
    return SignalCandidate(instrument="UNKNOWN", detected_at=ts, regime=regime, direction=direction, opportunities=opportunities, evidence=evidence, valid=valid, rejection_reason=reason)


def detect(df: pd.DataFrame, regime: Regime) -> list[SignalCandidate]:
    """Generate explainable candidates. This layer never sizes or executes trades."""
    if len(df) < 60:
        return [_candidate(df, Direction.NEUTRAL, tuple(), regime, {}, False, "INSUFFICIENT_DATA")]
    x = calculate_features(df)
    sf = structure_features(x)
    last = x.iloc[-1]
    candidates: list[SignalCandidate] = []

    if regime in {Regime.TREND_UP, Regime.EXPANSION, Regime.COMPRESSION} and sf.get("breakout_up"):
        evidence = {"close": float(last.close), "rsi14": float(last.rsi14), "range_atr": float(last.range_atr), "breakout_up": True}
        valid = bool(last.rsi14 >= 50 and last.range_atr < 3.0)
        candidates.append(_candidate(x, Direction.LONG, (Opportunity.BREAKOUT, Opportunity.MOMENTUM), regime, evidence, valid, None if valid else "BREAKOUT_CONFIRMATION_FAILED"))
    if regime in {Regime.TREND_DOWN, Regime.EXPANSION, Regime.COMPRESSION} and sf.get("breakout_down"):
        evidence = {"close": float(last.close), "rsi14": float(last.rsi14), "range_atr": float(last.range_atr), "breakout_down": True}
        valid = bool(last.rsi14 <= 50 and last.range_atr < 3.0)
        candidates.append(_candidate(x, Direction.SHORT, (Opportunity.BREAKOUT, Opportunity.MOMENTUM), regime, evidence, valid, None if valid else "BREAKOUT_CONFIRMATION_FAILED"))

    bullish = bool(last.close > last.ema20 > last.ema50 and last.roc10 > 0)
    bearish = bool(last.close < last.ema20 < last.ema50 and last.roc10 < 0)
    if regime == Regime.TREND_UP and bullish:
        candidates.append(_candidate(x, Direction.LONG, (Opportunity.TREND_CONTINUATION, Opportunity.PULLBACK), regime, {"ema20": float(last.ema20), "ema50": float(last.ema50), "roc10": float(last.roc10)}, True))
    if regime == Regime.TREND_DOWN and bearish:
        candidates.append(_candidate(x, Direction.SHORT, (Opportunity.TREND_CONTINUATION, Opportunity.PULLBACK), regime, {"ema20": float(last.ema20), "ema50": float(last.ema50), "roc10": float(last.roc10)}, True))
    return candidates
