from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

class Regime(str, Enum):
    TREND_UP = "TREND_UP"
    TRENDING = "TREND_UP"  # Backward-compatible alias for older callers/tests.
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    COMPRESSION = "COMPRESSION"
    EXPANSION = "EXPANSION"
    TRANSITION = "TRANSITION"
    NEWS_SHOCK = "NEWS_SHOCK"
    PROTECTION = "PROTECTION"

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"

class Opportunity(str, Enum):
    BREAKOUT = "BREAKOUT"
    PULLBACK = "PULLBACK"
    MOMENTUM = "MOMENTUM"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    REVERSAL = "REVERSAL"

@dataclass(frozen=True)
class SignalCandidate:
    instrument: str
    detected_at: datetime
    regime: Regime
    direction: Direction
    opportunities: tuple[Opportunity, ...]
    evidence: dict[str, Any] = field(default_factory=dict)
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    valid: bool = False
    rejection_reason: str | None = None
