from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

Direction = Literal["long", "short"]

@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    instrument: str
    direction: Direction
    units: float
    entry: float
    stop: float
    target: float
    created_at: datetime
    status: str = "open"

@dataclass(frozen=True)
class ClosedPaperTrade:
    order_id: str
    instrument: str
    direction: Direction
    units: float
    entry: float
    exit: float
    pnl: float
    reason: str
    opened_at: datetime
    closed_at: datetime

@dataclass
class PaperAccount:
    initial_equity: float = 10_000.0
    equity: float = field(init=False)
    orders: dict[str, PaperOrder] = field(default_factory=dict)
    closed_trades: list[ClosedPaperTrade] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        self.equity = float(self.initial_equity)

    def open_order(self, order: PaperOrder) -> PaperOrder:
        if order.order_id in self.orders:
            raise ValueError("order_id already exists")
        if order.units <= 0 or order.entry <= 0:
            raise ValueError("units and entry must be positive")
        if order.direction == "long" and not (order.stop < order.entry < order.target):
            raise ValueError("invalid long stop/target")
        if order.direction == "short" and not (order.target < order.entry < order.stop):
            raise ValueError("invalid short stop/target")
        self.orders[order.order_id] = order
        return order

    def mark_bar(self, instrument: str, high: float, low: float, close: float, at: datetime) -> list[ClosedPaperTrade]:
        closed = []
        for order in list(self.orders.values()):
            if order.instrument != instrument:
                continue
            reason = None
            exit_price = close
            if order.direction == "long":
                if low <= order.stop:
                    exit_price, reason = order.stop, "stop"
                elif high >= order.target:
                    exit_price, reason = order.target, "target"
            else:
                if high >= order.stop:
                    exit_price, reason = order.stop, "stop"
                elif low <= order.target:
                    exit_price, reason = order.target, "target"
            if reason is None:
                continue
            pnl = (exit_price - order.entry) * order.units
            if order.direction == "short":
                pnl = -pnl
            trade = ClosedPaperTrade(order.order_id, order.instrument, order.direction, order.units, order.entry, exit_price, pnl, reason, order.created_at, at)
            self.equity += pnl
            self.closed_trades.append(trade)
            del self.orders[order.order_id]
            closed.append(trade)
        return closed

    def snapshot(self) -> dict:
        return {
            "initial_equity": self.initial_equity,
            "equity": self.equity,
            "open_orders": len(self.orders),
            "closed_trades": len(self.closed_trades),
            "realized_pnl": sum(t.pnl for t in self.closed_trades),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
