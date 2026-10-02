from __future__ import annotations

from dataclasses import dataclass

from .risk import RiskDecision, RiskEngine


@dataclass(frozen=True)
class AccountRiskState:
    equity: float
    day_start_equity: float
    consecutive_losses: int = 0
    correlated_positions: int = 0
    protection: bool = False

    @property
    def daily_loss_pct(self) -> float:
        if self.day_start_equity <= 0:
            return 100.0
        return max(0.0, (self.day_start_equity - self.equity) / self.day_start_equity * 100)


class PaperRiskController:
    """Account-aware hard veto layer for paper trading."""

    def __init__(self, engine: RiskEngine | None = None) -> None:
        self.engine = engine or RiskEngine()

    def approve(self, state: AccountRiskState, risk_pct: float, *,
                spread_ok: bool = True, news_ok: bool = True) -> RiskDecision:
        return self.engine.approve(
            risk_pct=risk_pct,
            daily_loss_pct=state.daily_loss_pct,
            consecutive_losses=state.consecutive_losses,
            spread_ok=spread_ok,
            news_ok=news_ok,
            correlated_positions=state.correlated_positions,
            protection=state.protection,
        )
