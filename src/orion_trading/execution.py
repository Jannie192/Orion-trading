from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .models import Direction


@dataclass(frozen=True)
class OrderRequest:
    instrument: str
    direction: Direction
    units: float
    entry: float
    stop: float
    target: float | None
    client_order_id: str
    created_at: datetime


@dataclass(frozen=True)
class OrderResult:
    accepted: bool
    order_id: str | None
    reason: str


class ExecutionAdapter(Protocol):
    """Broker-neutral order execution boundary.

    Implementations may be paper, MT5, REST, FIX, or another broker adapter.
    Strategy and risk code must never depend on the concrete broker.
    """

    def submit(self, order: OrderRequest) -> OrderResult:
        """Submit an order without exposing broker-specific details."""

    def health_check(self) -> bool:
        """Return True only when the execution venue is healthy."""



class PaperExecution:
    """In-memory execution adapter. Safe default for research and paper trading."""

    def __init__(self) -> None:
        self.orders: list[OrderRequest] = []

    def health_check(self) -> bool:
        return True

    def submit(self, order: OrderRequest) -> OrderResult:
        if order.units <= 0:
            return OrderResult(False, None, "INVALID_UNITS")
        if order.entry <= 0 or order.stop <= 0:
            return OrderResult(False, None, "INVALID_PRICE")
        if order.direction is Direction.LONG and order.stop >= order.entry:
            return OrderResult(False, None, "INVALID_LONG_STOP")
        if order.direction is Direction.SHORT and order.stop <= order.entry:
            return OrderResult(False, None, "INVALID_SHORT_STOP")
        self.orders.append(order)
        return OrderResult(True, order.client_order_id, "ACCEPTED")
