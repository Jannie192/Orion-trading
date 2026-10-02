from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    max_risk_per_trade_pct: float = 0.50
    max_daily_loss_pct: float = 1.50
    max_consecutive_losses: int = 3
    max_correlated_exposure: int = 2


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskEngine:
    """Hard veto layer. No strategy component can override a rejection."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    def approve(self, *, risk_pct: float, daily_loss_pct: float, consecutive_losses: int,
                spread_ok: bool = True, news_ok: bool = True,
                correlated_positions: int = 0, protection: bool = False) -> RiskDecision:
        if protection:
            return RiskDecision(False, "PROTECTION_MODE")
        if risk_pct <= 0 or risk_pct > self.config.max_risk_per_trade_pct:
            return RiskDecision(False, "RISK_PER_TRADE_LIMIT")
        if daily_loss_pct >= self.config.max_daily_loss_pct:
            return RiskDecision(False, "DAILY_LOSS_LIMIT")
        if consecutive_losses >= self.config.max_consecutive_losses:
            return RiskDecision(False, "CONSECUTIVE_LOSS_LIMIT")
        if not spread_ok:
            return RiskDecision(False, "SPREAD_FILTER")
        if not news_ok:
            return RiskDecision(False, "NEWS_FILTER")
        if correlated_positions >= self.config.max_correlated_exposure:
            return RiskDecision(False, "CORRELATED_EXPOSURE_LIMIT")
        return RiskDecision(True, "APPROVED")
