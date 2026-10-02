from __future__ import annotations

from dataclasses import dataclass

from .models import Direction


@dataclass(frozen=True)
class PositionSize:
    units: float
    risk_amount: float
    stop_distance: float


def calculate_position_size(
    *,
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    value_per_price_unit: float = 1.0,
    min_units: float = 0.0,
    max_units: float | None = None,
) -> PositionSize:
    """Size from account equity and stop distance."""
    if equity <= 0:
        raise ValueError("equity must be positive")
    if risk_pct <= 0:
        raise ValueError("risk_pct must be positive")
    if entry <= 0 or stop <= 0:
        raise ValueError("entry and stop must be positive")
    if value_per_price_unit <= 0:
        raise ValueError("value_per_price_unit must be positive")
    distance = abs(entry - stop)
    if distance == 0:
        raise ValueError("entry and stop must differ")

    risk_amount = equity * risk_pct
    units = risk_amount / (distance * value_per_price_unit)
    units = max(units, min_units)
    if max_units is not None:
        if max_units <= 0:
            raise ValueError("max_units must be positive")
        units = min(units, max_units)
    return PositionSize(float(units), float(risk_amount), float(distance))


def direction_valid(direction: Direction, entry: float, stop: float) -> bool:
    if direction is Direction.LONG:
        return stop < entry
    if direction is Direction.SHORT:
        return stop > entry
    return False
