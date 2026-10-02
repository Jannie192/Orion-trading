from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Direction, SignalCandidate


@dataclass(frozen=True)
class ScoredSignal:
    candidate: SignalCandidate
    score: float
    confidence: str
    confirmations: tuple[str, ...]
    penalties: tuple[str, ...]


def score_candidate(
    candidate: SignalCandidate,
    *,
    timeframe: str,
    aligned_timeframes: Iterable[str] = (),
) -> ScoredSignal:
    score = 0.0
    confirmations: list[str] = []
    penalties: list[str] = []

    if candidate.valid:
        score += 40
        confirmations.append("VALID_SETUP")
    else:
        penalties.append("INVALID_SETUP")

    if candidate.regime.value in {"TREND_UP", "TREND_DOWN"}:
        score += 20
        confirmations.append("TREND_REGIME")
    elif candidate.regime.value in {"EXPANSION", "COMPRESSION"}:
        score += 10
        confirmations.append("VOLATILITY_REGIME")
    else:
        score -= 10
        penalties.append("NON_TREND_REGIME")

    for name in ("rsi14", "roc10"):
        value = candidate.evidence.get(name)
        if value is not None:
            if candidate.direction is Direction.LONG and ((name == "rsi14" and value >= 50) or (name == "roc10" and value > 0)):
                score += 5
                confirmations.append(f"{name.upper()}_ALIGNED")
            elif candidate.direction is Direction.SHORT and ((name == "rsi14" and value <= 50) or (name == "roc10" and value < 0)):
                score += 5
                confirmations.append(f"{name.upper()}_ALIGNED")

    aligned = set(aligned_timeframes)
    if aligned:
        score += min(15.0, 5.0 * len(aligned))
        confirmations.append("MTF_ALIGNMENT")

    score = max(0.0, min(100.0, score))
    confidence = "HIGH" if score >= 80 else "MEDIUM" if score >= 65 else "LOW"
    return ScoredSignal(candidate, score, confidence, tuple(confirmations), tuple(penalties))


def rank_signals(
    candidates: Iterable[tuple[str, SignalCandidate]],
) -> list[ScoredSignal]:
    items = list(candidates)
    out: list[ScoredSignal] = []
    for timeframe, candidate in items:
        same_direction = {
            tf for tf, other in items
            if other.instrument == candidate.instrument
            and other.direction == candidate.direction
            and other.valid
            and tf != timeframe
        }
        out.append(score_candidate(candidate, timeframe=timeframe, aligned_timeframes=same_direction))
    return sorted(out, key=lambda item: item.score, reverse=True)
