from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .execution import OrderRequest
from .models import Direction
from .paper_trading import PaperAccount


@dataclass(frozen=True)
class PaperDecision:
    accepted: bool
    order_id: str | None
    reason: str


class PaperTradingService:
    """Small orchestration layer for safe paper-only decision execution."""

    def __init__(self, account: PaperAccount | None = None) -> None:
        self.account = account or PaperAccount()

    def submit_plan(
        self,
        instrument: str,
        direction: Direction,
        units: float,
        entry: float,
        stop: float,
        target: float,
        created_at: datetime | None = None,
        client_order_id: str | None = None,
    ) -> PaperDecision:
        if direction not in (Direction.LONG, Direction.SHORT):
            return PaperDecision(False, None, "INVALID_DIRECTION")
        if units <= 0 or entry <= 0 or stop <= 0 or target <= 0:
            return PaperDecision(False, None, "INVALID_ORDER_VALUES")

        created_at = created_at or datetime.now(timezone.utc)
        order_id = client_order_id or f"paper-{uuid4().hex[:12]}"

        from .paper_trading import PaperOrder

        try:
            self.account.open_order(PaperOrder(
                order_id, instrument, direction.value.lower(), units,
                entry, stop, target, created_at
            ))
        except ValueError as exc:
            return PaperDecision(False, None, str(exc))

        return PaperDecision(True, order_id, "ACCEPTED")

    def on_bar(self, instrument: str, high: float, low: float, close: float, at: datetime):
        return self.account.mark_bar(instrument, high, low, close, at)

    def snapshot(self) -> dict:
        return self.account.snapshot()
