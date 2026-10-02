from __future__ import annotations

from datetime import datetime

from .execution import OrderRequest, OrderResult
from .paper_trading import PaperAccount, PaperOrder


class PaperAccountExecution:
    """Execution adapter backed by the paper-account position ledger."""

    def __init__(self, account: PaperAccount | None = None) -> None:
        self.account = account or PaperAccount()

    def submit(self, order: OrderRequest) -> OrderResult:
        if order.direction.value == "LONG":
            direction = "long"
        elif order.direction.value == "SHORT":
            direction = "short"
        else:
            return OrderResult(False, None, "INVALID_DIRECTION")

        if order.target is None:
            return OrderResult(False, None, "TARGET_REQUIRED")

        try:
            self.account.open_order(
                PaperOrder(
                    order_id=order.client_order_id,
                    instrument=order.instrument,
                    direction=direction,
                    units=order.units,
                    entry=order.entry,
                    stop=order.stop,
                    target=order.target,
                    created_at=order.created_at,
                )
            )
        except ValueError as exc:
            return OrderResult(False, None, str(exc))

        return OrderResult(True, order.client_order_id, "ACCEPTED")

    def mark_bar(
        self,
        instrument: str,
        high: float,
        low: float,
        close: float,
        at: datetime,
    ):
        return self.account.mark_bar(instrument, high, low, close, at)

    def snapshot(self) -> dict:
        return self.account.snapshot()
