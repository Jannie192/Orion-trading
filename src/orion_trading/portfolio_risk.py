from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import Direction, SignalCandidate


@dataclass(frozen=True)
class PortfolioPosition:
    instrument: str
    direction: Direction
    notional: float
    risk_amount: float


@dataclass(frozen=True)
class PortfolioDecision:
    approved: bool
    reason: str
    existing_risk_pct: float
    proposed_risk_pct: float
    resulting_risk_pct: float
    correlated_positions: int


@dataclass(frozen=True)
class PortfolioRiskConfig:
    max_total_risk_pct: float = 1.5
    max_instrument_risk_pct: float = 0.75
    max_correlated_positions: int = 2
    max_open_positions: int = 4


class PortfolioRiskGate:
    """Portfolio-level paper-trading gate.

    It prevents stacked exposure from multiple timeframes or correlated
    instruments. It does not submit or execute orders.
    """

    def __init__(self, config: PortfolioRiskConfig | None = None):
        self.config = config or PortfolioRiskConfig()

    def approve(
        self,
        *,
        equity: float,
        proposed_instrument: str,
        proposed_direction: Direction,
        proposed_risk_pct: float,
        positions: Iterable[PortfolioPosition],
    ) -> PortfolioDecision:
        if equity <= 0:
            return PortfolioDecision(False, "INVALID_EQUITY", 0, proposed_risk_pct, proposed_risk_pct, 0)

        current = list(positions)
        existing_risk_pct = sum((p.risk_amount / equity) * 100 for p in current)
        same_instrument = [
            p for p in current if p.instrument == proposed_instrument
        ]
        correlated = len(same_instrument)

        instrument_risk_pct = sum((p.risk_amount / equity) * 100 for p in same_instrument)

        if len(current) >= self.config.max_open_positions:
            return PortfolioDecision(False, "MAX_OPEN_POSITIONS", existing_risk_pct, proposed_risk_pct, existing_risk_pct + proposed_risk_pct, correlated)

        if correlated >= self.config.max_correlated_positions:
            return PortfolioDecision(False, "MAX_CORRELATED_POSITIONS", existing_risk_pct, proposed_risk_pct, existing_risk_pct + proposed_risk_pct, correlated)

        if instrument_risk_pct + proposed_risk_pct > self.config.max_instrument_risk_pct:
            return PortfolioDecision(False, "MAX_INSTRUMENT_RISK", existing_risk_pct, proposed_risk_pct, existing_risk_pct + proposed_risk_pct, correlated)

        resulting = existing_risk_pct + proposed_risk_pct
        if resulting > self.config.max_total_risk_pct:
            return PortfolioDecision(False, "MAX_TOTAL_PORTFOLIO_RISK", existing_risk_pct, proposed_risk_pct, resulting, correlated)

        return PortfolioDecision(True, "PORTFOLIO_RISK_APPROVED", existing_risk_pct, proposed_risk_pct, resulting, correlated)
