from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from .supabase_paper_store import SupabasePaperStore
from .supabase_strategy_store import SupabaseStrategyStore


@dataclass(frozen=True)
class PaperPromotionConfig:
    min_trades: int = 30
    min_days: int = 30
    min_expectancy_r: float = 0.0
    min_profit_factor: float = 1.10
    max_drawdown_pct: float = 15.0
    max_consecutive_losses: int = 8


@dataclass(frozen=True)
class PaperPerformance:
    strategy_id: str
    status: str
    eligible: bool
    reason: str
    days_in_paper: int
    trades: int
    wins: int
    losses: int
    win_rate_pct: float
    net_pnl: float
    average_r: float
    expectancy_r: float
    profit_factor: float | None
    max_drawdown_pct: float
    max_consecutive_losses: int


class PaperPerformanceEngine:
    """Measure forward paper results and gate PAPER_CANDIDATE -> PAPER_ACTIVE."""

    def __init__(
        self,
        paper_store: SupabasePaperStore,
        strategy_store: SupabaseStrategyStore,
        config: PaperPromotionConfig | None = None,
    ) -> None:
        self.paper_store = paper_store
        self.strategy_store = strategy_store
        self.config = config or PaperPromotionConfig()

    @staticmethod
    def _days_in_paper(trades: list[dict[str, Any]]) -> int:
        if not trades:
            return 0
        timestamps = []
        for trade in trades:
            for key in ("opened_at", "closed_at"):
                value = trade.get(key)
                if value:
                    timestamps.append(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
        if not timestamps:
            return 0
        start = min(timestamps)
        end = max(timestamps)
        return max(0, (end - start).days)

    @staticmethod
    def _drawdown_pct(trades: list[dict[str, Any]], initial_equity: float) -> float:
        if initial_equity <= 0:
            return 0.0
        equity = initial_equity
        peak = equity
        max_dd = 0.0
        for trade in sorted(trades, key=lambda t: t.get("closed_at", "")):
            equity += float(trade["pnl"])
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100 if peak else 0.0)
        return max_dd

    def evaluate(self, candidate: dict[str, Any]) -> PaperPerformance:
        strategy_id = str(candidate["strategy_id"])
        trades = [
            t for t in self.paper_store.closed_trades()
            if str(t.get("strategy_id") or "") == strategy_id
        ]
        account = self.paper_store.account()
        initial = float(account["initial_equity"])
        wins = sum(1 for t in trades if float(t["pnl"]) > 0)
        losses = sum(1 for t in trades if float(t["pnl"]) < 0)
        net_pnl = sum(float(t["pnl"]) for t in trades)
        r_values = [
            float(t["pnl"]) / float(t["risk_amount"])
            for t in trades
            if float(t.get("risk_amount") or 0) > 0
        ]
        average_r = sum(r_values) / len(r_values) if r_values else 0.0
        gross_profit = sum(float(t["pnl"]) for t in trades if float(t["pnl"]) > 0)
        gross_loss = abs(sum(float(t["pnl"]) for t in trades if float(t["pnl"]) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else None)

        max_streak = 0
        streak = 0
        for trade in sorted(trades, key=lambda t: t.get("closed_at", "")):
            if float(trade["pnl"]) < 0:
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0

        days = self._days_in_paper(trades)
        dd = self._drawdown_pct(trades, initial)
        cfg = self.config
        checks = [
            len(trades) >= cfg.min_trades,
            days >= cfg.min_days,
            average_r >= cfg.min_expectancy_r,
            profit_factor is not None and profit_factor >= cfg.min_profit_factor,
            dd <= cfg.max_drawdown_pct,
            max_streak <= cfg.max_consecutive_losses,
        ]
        eligible = all(checks)

        if eligible:
            reason = "PROMOTION_GATE_PASSED"
        else:
            failed = []
            labels = ("MIN_TRADES", "MIN_DAYS", "MIN_EXPECTANCY_R", "MIN_PROFIT_FACTOR", "MAX_DRAWDOWN", "MAX_LOSING_STREAK")
            failed = [label for label, ok in zip(labels, checks) if not ok]
            reason = "FAILED:" + ",".join(failed)

        return PaperPerformance(
            strategy_id=strategy_id,
            status=str(candidate.get("status") or ""),
            eligible=eligible,
            reason=reason,
            days_in_paper=days,
            trades=len(trades),
            wins=wins,
            losses=losses,
            win_rate_pct=(wins / len(trades) * 100) if trades else 0.0,
            net_pnl=net_pnl,
            average_r=average_r,
            expectancy_r=average_r,
            profit_factor=profit_factor,
            max_drawdown_pct=dd,
            max_consecutive_losses=max_streak,
        )

    def evaluate_and_promote(self, candidate: dict[str, Any]) -> PaperPerformance:
        result = self.evaluate(candidate)
        payload = {
            "validation": {
                **(candidate.get("validation") or {}),
                "paper_performance": asdict(result),
                "paper_promotion_config": asdict(self.config),
            }
        }
        if result.eligible:
            self.strategy_store.update_version(
                result.strategy_id,
                {**payload, "status": "PAPER_ACTIVE"},
            )
        else:
            self.strategy_store.update_version(result.strategy_id, payload)
        return result
