from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping

import pandas as pd

from .backtest import BacktestConfig, BacktestResult, Backtester


@dataclass(frozen=True)
class MarketBacktestSummary:
    instrument: str
    rows: int
    result: BacktestResult


@dataclass(frozen=True)
class MultiMarketBacktestResult:
    initial_equity_per_market: float
    markets: tuple[MarketBacktestSummary, ...]

    @property
    def total_trades(self) -> int:
        return sum(item.result.wins + item.result.losses for item in self.markets)

    @property
    def profitable_markets(self) -> int:
        return sum(item.result.final_equity > item.result.initial_equity for item in self.markets)

    def as_records(self) -> list[dict]:
        records = []
        for item in self.markets:
            result = item.result
            records.append(
                {
                    "instrument": item.instrument,
                    "rows": item.rows,
                    "trades": len(result.trades),
                    "wins": result.wins,
                    "losses": result.losses,
                    "win_rate_pct": result.win_rate_pct,
                    "profit_factor": result.profit_factor,
                    "return_pct": result.total_return_pct,
                    "max_drawdown_pct": result.max_drawdown_pct,
                    "final_equity": result.final_equity,
                }
            )
        return records


def run_multi_market_backtest(
    markets: Mapping[str, pd.DataFrame],
    *,
    config: BacktestConfig | None = None,
    backtester: Backtester | None = None,
) -> MultiMarketBacktestResult:
    """Run identical research rules independently across several markets.

    Each market receives the same starting equity. Results are deliberately kept
    separate so cross-market performance cannot be mistaken for a shared-capital
    portfolio result.
    """
    config = config or BacktestConfig()
    summaries: list[MarketBacktestSummary] = []

    for instrument, candles in markets.items():
        engine = Backtester(config=config) if backtester is None else backtester
        result = engine.run(candles, instrument=instrument)
        summaries.append(MarketBacktestSummary(instrument, len(candles), result))

    return MultiMarketBacktestResult(
        initial_equity_per_market=config.initial_equity,
        markets=tuple(summaries),
    )


def results_frame(result: MultiMarketBacktestResult) -> pd.DataFrame:
    return pd.DataFrame(result.as_records())
