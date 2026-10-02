from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class JournalTrade:
    order_id: str
    instrument: str
    direction: str
    entry: float
    exit: float
    units: float
    pnl: float
    risk_amount: float
    reason: str
    regime: str | None = None
    signal_type: str | None = None

    @property
    def r_multiple(self) -> float:
        return self.pnl / self.risk_amount if self.risk_amount > 0 else 0.0


@dataclass(frozen=True)
class PerformanceSnapshot:
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    net_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    expectancy_r: float
    average_r: float
    max_consecutive_losses: int
    max_drawdown_pct: float


class TradeJournal:
    """Immutable-style trade journal and descriptive performance calculator."""

    def __init__(self) -> None:
        self._trades: list[JournalTrade] = []

    def record(self, trade: JournalTrade) -> None:
        if trade.pnl == 0:
            raise ValueError("trade pnl must not be zero")
        if trade.risk_amount <= 0:
            raise ValueError("risk_amount must be positive")
        if any(t.order_id == trade.order_id for t in self._trades):
            raise ValueError("order_id already recorded")
        self._trades.append(trade)

    @property
    def trades(self) -> tuple[JournalTrade, ...]:
        return tuple(self._trades)

    def snapshot(self, initial_equity: float = 10_000.0) -> PerformanceSnapshot:
        if initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        trades = self._trades
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        net_pnl = sum(t.pnl for t in trades)
        r_values = [t.r_multiple for t in trades]
        equity = peak = initial_equity
        max_dd = 0.0
        streak = max_streak = 0
        for trade in trades:
            equity += trade.pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100)
            streak = streak + 1 if trade.pnl < 0 else 0
            max_streak = max(max_streak, streak)
        return PerformanceSnapshot(
            trades=len(trades), wins=len(wins), losses=len(losses),
            win_rate_pct=(len(wins) / len(trades) * 100) if trades else 0.0,
            net_pnl=net_pnl, gross_profit=gross_profit, gross_loss=gross_loss,
            profit_factor=(gross_profit / gross_loss) if gross_loss else None,
            expectancy_r=(sum(r_values) / len(r_values)) if r_values else 0.0,
            average_r=(sum(r_values) / len(r_values)) if r_values else 0.0,
            max_consecutive_losses=max_streak, max_drawdown_pct=max_dd,
        )

    def grouped(self, field: str) -> dict[str, PerformanceSnapshot]:
        if field not in {"instrument", "regime", "signal_type", "direction", "reason"}:
            raise ValueError("unsupported grouping field")
        groups: dict[str, TradeJournal] = {}
        for trade in self._trades:
            key = getattr(trade, field) or "UNKNOWN"
            groups.setdefault(str(key), TradeJournal()).record(trade)
        return {key: journal.snapshot() for key, journal in groups.items()}
