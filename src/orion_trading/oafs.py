from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from .features import calculate_features, structure_features
from .models import Direction, Opportunity, Regime, SignalCandidate
from .mtf import MTFContext

@dataclass(frozen=True)
class OAFSConfig:
    min_bars: int = 100
    breakout_lookback: int = 20
    max_range_atr: float = 3.0
    max_extension_atr: float = 2.5

def _candidate(frame, instrument, direction, ops, regime, evidence, valid, reason=None):
    ts = frame.index[-1]
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    return SignalCandidate(instrument=instrument, detected_at=ts, regime=regime,
        direction=direction, opportunities=tuple(ops), evidence=evidence,
        valid=valid, rejection_reason=reason)

def generate_candidates(frames: dict[str, pd.DataFrame], context: MTFContext,
                        instrument: str, config: OAFSConfig | None = None):
    cfg = config or OAFSConfig()
    m15 = frames["M15"]
    if len(m15) < cfg.min_bars:
        return [_candidate(m15, instrument, Direction.NEUTRAL, [], context.regime, {},
                            False, "INSUFFICIENT_DATA")]
    x = calculate_features(m15)
    s = structure_features(x, cfg.breakout_lookback)
    last = x.iloc[-1]
    out = []
    if context.regime in {Regime.NEWS_SHOCK, Regime.PROTECTION}:
        return [_candidate(x, instrument, Direction.NEUTRAL, [], context.regime, {},
                            False, "REGIME_BLOCKED")]
    bull = context.h4_bullish and context.h1_bullish and not context.d1_bearish
    bear = context.h4_bearish and context.h1_bearish and not context.d1_bullish
    atr = float(last.atr14) if pd.notna(last.atr14) else 0.0
    extension = abs(float(last.close) - float(last.ema20)) / atr if atr > 0 else 99.0
    if s.get("breakout_up") and bull:
        valid = bool(last.rsi14 >= 50 and last.range_atr < cfg.max_range_atr and extension < cfg.max_extension_atr)
        out.append(_candidate(x, instrument, Direction.LONG, [Opportunity.BREAKOUT, Opportunity.MOMENTUM],
            context.regime, {"breakout":"up","rsi14":float(last.rsi14),"range_atr":float(last.range_atr),
            "extension_atr":extension}, valid, None if valid else "BREAKOUT_CONFIRMATION_FAILED"))
    if s.get("breakout_down") and bear:
        valid = bool(last.rsi14 <= 50 and last.range_atr < cfg.max_range_atr and extension < cfg.max_extension_atr)
        out.append(_candidate(x, instrument, Direction.SHORT, [Opportunity.BREAKOUT, Opportunity.MOMENTUM],
            context.regime, {"breakout":"down","rsi14":float(last.rsi14),"range_atr":float(last.range_atr),
            "extension_atr":extension}, valid, None if valid else "BREAKOUT_CONFIRMATION_FAILED"))
    pullback_long = bull and last.close > last.ema50 and last.close <= last.ema20 and last.roc10 > -0.005
    pullback_short = bear and last.close < last.ema50 and last.close >= last.ema20 and last.roc10 < 0.005
    if pullback_long:
        out.append(_candidate(x, instrument, Direction.LONG, [Opportunity.PULLBACK, Opportunity.TREND_CONTINUATION],
            context.regime, {"ema20":float(last.ema20),"ema50":float(last.ema50),"roc10":float(last.roc10)}, True))
    if pullback_short:
        out.append(_candidate(x, instrument, Direction.SHORT, [Opportunity.PULLBACK, Opportunity.TREND_CONTINUATION],
            context.regime, {"ema20":float(last.ema20),"ema50":float(last.ema50),"roc10":float(last.roc10)}, True))
    momentum_long = bull and last.roc10 > 0 and last.rsi14 >= 55 and extension < cfg.max_extension_atr
    momentum_short = bear and last.roc10 < 0 and last.rsi14 <= 45 and extension < cfg.max_extension_atr
    if momentum_long:
        out.append(_candidate(x, instrument, Direction.LONG, [Opportunity.MOMENTUM], context.regime,
            {"roc10":float(last.roc10),"rsi14":float(last.rsi14),"extension_atr":extension}, True))
    if momentum_short:
        out.append(_candidate(x, instrument, Direction.SHORT, [Opportunity.MOMENTUM], context.regime,
            {"roc10":float(last.roc10),"rsi14":float(last.rsi14),"extension_atr":extension}, True))
    return out
