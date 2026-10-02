from __future__ import annotations

from dataclasses import dataclass
from .models import Direction, Opportunity

@dataclass(frozen=True)
class TradePlan:
    instrument: str
    direction: Direction
    opportunity: Opportunity
    entry: float
    stop: float
    target: float
    risk_fraction: float
    invalidation: str

def build_plan(instrument: str, direction: Direction, opportunity: Opportunity, entry: float, stop: float, reward_multiple: float = 2.0, risk_fraction: float = 0.005) -> TradePlan:
    if direction not in (Direction.LONG, Direction.SHORT):
        raise ValueError("A trade plan requires LONG or SHORT direction")
    if entry == stop:
        raise ValueError("Entry and stop must differ")
    distance = abs(entry - stop)
    target = entry + distance * reward_multiple if direction is Direction.LONG else entry - distance * reward_multiple
    return TradePlan(instrument, direction, opportunity, entry, stop, target, risk_fraction, "structural invalidation beyond stop")
