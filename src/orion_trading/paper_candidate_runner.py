from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .supabase_market_store import SupabaseMarketDataStore
from .supabase_paper_store import SupabasePaperStore
from .supabase_strategy_store import SupabaseStrategyStore
from .trading_engine import TradingEngine, TradingEngineConfig


@dataclass(frozen=True)
class CandidateRunResult:
    strategy_id: str
    instrument: str
    timeframe: str
    closed_trades: int
    submitted_orders: int
    skipped_duplicates: int
    plans: int


class PaperCandidateRunner:
    """Execute approved research candidates against the persistent paper ledger."""

    def __init__(self, market_store: SupabaseMarketDataStore, paper_store: SupabasePaperStore, strategy_store: SupabaseStrategyStore):
        self.market_store = market_store
        self.paper_store = paper_store
        self.strategy_store = strategy_store

    def candidates(self, instrument: str | None = None, timeframe: str | None = None) -> list[dict[str, Any]]:
        rows = self.strategy_store.versions()
        return [
            row for row in rows
            if row.get("status") == "PAPER_CANDIDATE"
            and (instrument is None or row.get("instrument") == instrument)
            and (timeframe is None or row.get("timeframe", "").upper() == timeframe.upper())
        ]

    def run_candidate(self, candidate: dict[str, Any], candles: pd.DataFrame | None = None) -> CandidateRunResult:
        instrument = str(candidate["instrument"])
        timeframe = str(candidate["timeframe"]).upper()
        parameters = candidate.get("candidate_parameters") or {}
        engine = TradingEngine(config=TradingEngineConfig(
            risk_per_trade_pct=float(parameters.get("risk_per_trade_pct", 0.50)),
            atr_stop_multiple=float(parameters.get("atr_stop_multiple", 1.5)),
            reward_multiple=float(parameters.get("reward_multiple", 2.0)),
        ))
        frame = candles if candles is not None else self.market_store.load(instrument, timeframe, limit=500)
        if frame.empty:
            return CandidateRunResult(str(candidate["strategy_id"]), instrument, timeframe, 0, 0, 0, 0)

        row = frame.iloc[-1]
        closed = self.paper_store.mark_bar(
            instrument,
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            frame.index[-1].to_pydatetime(),
        )
        equity = float(self.paper_store.snapshot()["account"]["equity"])
        evaluation = engine.evaluate(frame, instrument=instrument, equity=equity)

        submitted = 0
        duplicates = 0
        for plan in evaluation.plans:
            if plan.order is None or not plan.risk.approved:
                continue
            order = {
                "order_id": plan.order.client_order_id,
                "instrument": instrument,
                "timeframe": timeframe,
                "direction": "long" if plan.order.direction.value == "LONG" else "short",
                "units": plan.order.units,
                "entry": plan.order.entry,
                "stop": plan.order.stop,
                "target": plan.order.target,
                "regime": plan.candidate.regime.value,
                "signal_type": ",".join(x.value for x in plan.candidate.opportunities),
                "detected_at": plan.order.created_at.isoformat(),
            }
            if self.paper_store.has_order(order["order_id"]):
                duplicates += 1
                continue
            self.paper_store.create_order(order)
            submitted += 1

        return CandidateRunResult(
            str(candidate["strategy_id"]), instrument, timeframe,
            len(closed), submitted, duplicates, len(evaluation.plans),
        )
