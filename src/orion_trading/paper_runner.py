from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import Direction
from .paper_journal_bridge import PaperJournalBridge
from .paper_trading import ClosedPaperTrade, PaperAccount
from .risk import RiskEngine
from .trade_journal import TradeJournal


@dataclass(frozen=True)
class PaperRunDecision:
    accepted: bool
    order_id: str | None
    reason: str


class PaperRunner:
    """Runs approved plans through risk, paper execution, and journaling."""

    def __init__(
        self,
        account: PaperAccount | None = None,
        journal: TradeJournal | None = None,
        risk_engine: RiskEngine | None = None,
    ) -> None:
        self.account = account or PaperAccount()
        self.journal = journal or TradeJournal()
        self.risk_engine = risk_engine or RiskEngine()
        self.bridge = PaperJournalBridge(self.journal)
        self._risk_by_order: dict[str, float] = {}
        self._metadata_by_order: dict[str, dict] = {}

    def submit(
        self,
        *,
        order_id: str,
        instrument: str,
        direction: Direction,
        units: float,
        entry: float,
        stop: float,
        target: float,
        risk_pct: float,
        daily_loss_pct: float = 0.0,
        consecutive_losses: int = 0,
        correlated_positions: int = 0,
        spread_ok: bool = True,
        news_ok: bool = True,
        protection: bool = False,
        regime: str | None = None,
        signal_type: str | None = None,
        created_at: datetime | None = None,
    ) -> PaperRunDecision:
        decision = self.risk_engine.approve(
            risk_pct=risk_pct,
            daily_loss_pct=daily_loss_pct,
            consecutive_losses=consecutive_losses,
            spread_ok=spread_ok,
            news_ok=news_ok,
            correlated_positions=correlated_positions,
            protection=protection,
        )
        if not decision.approved:
            return PaperRunDecision(False, None, decision.reason)

        from .paper_trading import PaperOrder
        try:
            self.account.open_order(PaperOrder(
                order_id, instrument, direction.value.lower(), units,
                entry, stop, target, created_at or datetime.utcnow()
            ))
        except ValueError as exc:
            return PaperRunDecision(False, None, str(exc))

        self._risk_by_order[order_id] = self.account.equity * risk_pct / 100
        self._metadata_by_order[order_id] = {
            "regime": regime, "signal_type": signal_type
        }
        return PaperRunDecision(True, order_id, "ACCEPTED")

    def on_bar(self, instrument: str, high: float, low: float, close: float, at: datetime) -> list[ClosedPaperTrade]:
        closed = self.account.mark_bar(instrument, high, low, close, at)
        self.bridge.sync(closed, self._risk_by_order, self._metadata_by_order)
        return closed

    def performance(self):
        return self.journal.snapshot()

    def snapshot(self) -> dict:
        return {
            **self.account.snapshot(),
            "performance": self.performance().__dict__,
        }
