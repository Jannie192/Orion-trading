from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .supabase_market_store import SupabaseMarketDataStore
from .supabase_paper_store import SupabasePaperStore
from .supabase_strategy_store import SupabaseStrategyStore
from .execution import OrderRequest, OrderResult
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


class PersistentPaperExecution:
    """Execution adapter that writes approved orders to the persistent paper ledger."""

    def __init__(
        self,
        paper_store: SupabasePaperStore,
        timeframe: str,
        strategy_id: str | None = None,
        strategy_name: str | None = None,
        strategy_version: str | None = None,
        source_experiment_id: str | None = None,
    ) -> None:
        self.paper_store = paper_store
        self.timeframe = timeframe
        self._strategy_id = strategy_id
        self._strategy_name = strategy_name
        self._strategy_version = strategy_version
        self._source_experiment_id = source_experiment_id

    def submit(self, order: OrderRequest) -> OrderResult:
        if order.units <= 0:
            return OrderResult(False, None, "INVALID_UNITS")
        if order.entry <= 0 or order.stop <= 0:
            return OrderResult(False, None, "INVALID_PRICE")
        if order.direction.value == "LONG" and order.stop >= order.entry:
            return OrderResult(False, None, "INVALID_LONG_STOP")
        if order.direction.value == "SHORT" and order.stop <= order.entry:
            return OrderResult(False, None, "INVALID_SHORT_STOP")
        if self.paper_store.has_order(order.client_order_id):
            return OrderResult(False, order.client_order_id, "DUPLICATE_ORDER")
        self.paper_store.create_order({
            "order_id": order.client_order_id,
            "instrument": order.instrument,
            "timeframe": self.timeframe,
            "direction": "long" if order.direction.value == "LONG" else "short",
            "units": order.units,
            "entry": order.entry,
            "stop": order.stop,
            "target": order.target,
            "detected_at": order.created_at.isoformat(),
            "strategy_id": self._strategy_id,
            "strategy_name": self._strategy_name,
            "strategy_version": self._strategy_version,
            "source_experiment_id": self._source_experiment_id,
        })
        return OrderResult(True, order.client_order_id, "ACCEPTED")


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
        execution = PersistentPaperExecution(
            self.paper_store,
            timeframe,
            str(candidate["strategy_id"]),
            str(candidate.get("name") or candidate.get("strategy_name") or "ORION"),
            str(candidate.get("version") or candidate.get("strategy_version") or "1.0"),
            candidate.get("source_experiment_id"),
        )
        evaluation = engine.evaluate(frame, instrument=instrument, equity=equity, execution=execution)

        submitted = 0
        duplicates = 0
        for plan in evaluation.plans:
            if plan.order is None or not plan.risk.approved:
                continue
            if plan.order.accepted:
                submitted += 1
            elif plan.order.reason == "DUPLICATE_ORDER":
                duplicates += 1

        return CandidateRunResult(
            str(candidate["strategy_id"]), instrument, timeframe,
            len(closed), submitted, duplicates, len(evaluation.plans),
        )
