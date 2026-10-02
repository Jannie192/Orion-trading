from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable

from .position_sizing import calculate_position_size
from .signals import SignalCandidate
from .supabase_paper_store import SupabasePaperStore


@dataclass(frozen=True)
class PaperSignalDecision:
    accepted: bool
    order_id: str | None
    reason: str


class PaperSignalService:
    """Turns validated scanner candidates into persistent paper orders only."""

    def __init__(self, store: SupabasePaperStore, risk_pct: float = 0.005) -> None:
        if not 0 < risk_pct <= 0.005:
            raise ValueError("risk_pct must be between 0 and 0.005")
        self.store = store
        self.risk_pct = risk_pct

    @staticmethod
    def order_id(candidate: SignalCandidate, timeframe: str) -> str:
        raw = f"{candidate.instrument}|{timeframe}|{candidate.direction.value}|{candidate.detected_at.isoformat()}"
        return "paper-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    def submit(self, candidate: SignalCandidate, timeframe: str) -> PaperSignalDecision:
        if not candidate.valid:
            return PaperSignalDecision(False, None, candidate.rejection_reason or "INVALID_SIGNAL")
        if candidate.entry is None or candidate.stop is None or candidate.target is None:
            return PaperSignalDecision(False, None, "MISSING_TRADE_LEVELS")

        order_id = self.order_id(candidate, timeframe)
        if self.store.has_order(order_id):
            return PaperSignalDecision(False, order_id, "DUPLICATE_SIGNAL")

        account = self.store.account()
        equity = float(account["initial_equity"]) + sum(float(t["pnl"]) for t in self.store.closed_trades())
        size = calculate_position_size(
            equity=equity,
            risk_pct=self.risk_pct,
            entry=float(candidate.entry),
            stop=float(candidate.stop),
        )
        signal_type = candidate.opportunities[0].value if candidate.opportunities else "unknown"
        # Supabase stores direction in lowercase; the domain model remains enum-based.
        db_direction = candidate.direction.value.lower()
        self.store.create_order({
            "order_id": order_id,
            "instrument": candidate.instrument,
            "timeframe": timeframe,
            "direction": db_direction,
            "units": size.units,
            "entry": float(candidate.entry),
            "stop": float(candidate.stop),
            "target": float(candidate.target),
            "regime": candidate.regime.value,
            "signal_type": signal_type,
            "detected_at": candidate.detected_at.isoformat(),
        })
        return PaperSignalDecision(True, order_id, "ACCEPTED")


def submit_candidates(store: SupabasePaperStore, candidates: Iterable[tuple[str, SignalCandidate]]) -> list[PaperSignalDecision]:
    service = PaperSignalService(store)
    return [service.submit(candidate, timeframe) for timeframe, candidate in candidates]
