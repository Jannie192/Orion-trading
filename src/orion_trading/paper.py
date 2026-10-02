from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import Direction


@dataclass(frozen=True)
class PaperOrder:
    instrument: str
    direction: Direction
    units: float
    entry: float
    stop: float
    target: float | None
    created_at: datetime


class PaperBroker:
    """Deterministic paper broker. It never sends orders to a real broker."""

    def __init__(self):
        self.orders: list[PaperOrder] = []

    def submit(self, order: PaperOrder) -> PaperOrder:
        self.orders.append(order)
        return order
