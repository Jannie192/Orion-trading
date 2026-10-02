from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from .execution import ExecutionAdapter, OrderRequest, OrderResult
from .features import calculate_features
from .models import Direction, Regime, SignalCandidate
from .position_sizing import PositionSize, calculate_position_size, direction_valid
from .regime import classify_regime
from .risk import RiskDecision, RiskEngine
from .signals import detect


@dataclass(frozen=True)
class TradingEngineConfig:
    """Broker-neutral controls for turning research signals into paper orders."""
    risk_per_trade_pct: float = 0.50
    atr_stop_multiple: float = 1.5
    reward_multiple: float = 2.0
    min_signal_score: float = 0.0


@dataclass(frozen=True)
class TradePlan:
    candidate: SignalCandidate
    entry: float
    stop: float
    target: float
    position: PositionSize
    risk: RiskDecision
    order: OrderRequest | None = None


@dataclass(frozen=True)
class Evaluation:
    plans: tuple[TradePlan, ...]
    executions: tuple[OrderResult, ...]


class TradingEngine:
    """Single decision pipeline: data -> regime -> signal -> risk -> sizing -> execution.

    Execution is injected, so the same engine can run against paper or a future
    broker adapter without changing strategy logic.
    """

    def __init__(
        self,
        *,
        risk_engine: RiskEngine | None = None,
        config: TradingEngineConfig | None = None,
    ) -> None:
        self.risk_engine = risk_engine or RiskEngine()
        self.config = config or TradingEngineConfig()

    def evaluate(
        self,
        candles: pd.DataFrame,
        *,
        instrument: str,
        equity: float,
        execution: ExecutionAdapter | None = None,
        daily_loss_pct: float = 0.0,
        consecutive_losses: int = 0,
        spread_ok: bool = True,
        news_ok: bool = True,
        correlated_positions: int = 0,
        protection: bool = False,
    ) -> Evaluation:
        if candles.empty or len(candles) < 60:
            return Evaluation((), ())

        features = calculate_features(candles).dropna()
        if features.empty:
            return Evaluation((), ())

        regime, _ = classify_regime(candles)
        candidates = detect(candles, regime, instrument)
        plans: list[TradePlan] = []
        executions: list[OrderResult] = []

        for candidate in candidates:
            if not candidate.valid or candidate.direction is Direction.NEUTRAL:
                continue

            last = features.iloc[-1]
            entry = float(last["close"])
            atr = float(last["atr14"])
            if not pd.notna(atr) or atr <= 0:
                continue

            distance = atr * self.config.atr_stop_multiple
            stop = entry - distance if candidate.direction is Direction.LONG else entry + distance
            target = entry + distance * self.config.reward_multiple if candidate.direction is Direction.LONG else entry - distance * self.config.reward_multiple

            if not direction_valid(candidate.direction, entry, stop):
                continue

            risk_pct_fraction = self.config.risk_per_trade_pct / 100.0
            position = calculate_position_size(
                equity=equity,
                risk_pct=risk_pct_fraction,
                entry=entry,
                stop=stop,
            )
            risk = self.risk_engine.approve(
                risk_pct=self.config.risk_per_trade_pct,
                daily_loss_pct=daily_loss_pct,
                consecutive_losses=consecutive_losses,
                spread_ok=spread_ok,
                news_ok=news_ok,
                correlated_positions=correlated_positions,
                protection=protection,
            )

            order = None
            if risk.approved and execution is not None:
                order = OrderRequest(
                    instrument=instrument,
                    direction=candidate.direction,
                    units=position.units,
                    entry=entry,
                    stop=stop,
                    target=target,
                    client_order_id=self._order_id(instrument, candidate),
                    created_at=candidate.detected_at,
                )
                executions.append(execution.submit(order))

            plans.append(TradePlan(candidate, entry, stop, target, position, risk, order))

        return Evaluation(tuple(plans), tuple(executions))

    @staticmethod
    def _order_id(instrument: str, candidate: SignalCandidate) -> str:
        stamp = candidate.detected_at.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"ORION-{instrument}-{candidate.direction.value}-{stamp}"
