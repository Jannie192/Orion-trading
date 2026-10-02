from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionCostConfig:
    spread_bps: float = 0.0
    slippage_bps: float = 0.0
    commission_r: float = 0.0

def round_trip_r(entry: float, stop_distance: float, config: ExecutionCostConfig) -> float:
    if entry <= 0 or stop_distance <= 0:
        return 0.0
    price_cost = entry * (2.0 * (config.spread_bps + config.slippage_bps) / 10_000.0)
    return price_cost / stop_distance + config.commission_r

def apply_cost(pnl_r: float, entry: float, stop_distance: float, config: ExecutionCostConfig) -> float:
    return float(pnl_r - round_trip_r(entry, stop_distance, config))
