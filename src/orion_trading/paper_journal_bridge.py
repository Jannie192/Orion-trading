from __future__ import annotations

from .trade_journal import JournalTrade


class PaperJournalBridge:
    """Converts closed paper trades into journal records."""

    def __init__(self, journal) -> None:
        self.journal = journal
        self._recorded: set[str] = set()

    def sync(self, closed_trades, risk_amount_by_order: dict[str, float], metadata_by_order: dict[str, dict] | None = None) -> int:
        metadata_by_order = metadata_by_order or {}
        added = 0
        for trade in closed_trades:
            if trade.order_id in self._recorded:
                continue
            risk = risk_amount_by_order.get(trade.order_id)
            if risk is None or risk <= 0:
                continue
            meta = metadata_by_order.get(trade.order_id, {})
            self.journal.record(JournalTrade(
                order_id=trade.order_id,
                instrument=trade.instrument,
                direction=trade.direction,
                entry=trade.entry,
                exit=trade.exit,
                units=trade.units,
                pnl=trade.pnl,
                risk_amount=risk,
                reason=trade.reason,
                regime=meta.get("regime"),
                signal_type=meta.get("signal_type"),
            ))
            self._recorded.add(trade.order_id)
            added += 1
        return added
