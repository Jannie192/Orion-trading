from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .backtest import BacktestConfig, BacktestResult, Backtester
from .multi_market_backtest import MultiMarketBacktestResult, run_multi_market_backtest
from .research_universe import DEFAULT_UNIVERSE


@dataclass(frozen=True)
class ResearchRun:
    """Container for a reproducible batch research run.

    Missing markets are reported rather than silently substituted.
    """

    requested: tuple[str, ...]
    available: tuple[str, ...]
    missing: tuple[str, ...]
    backtest: MultiMarketBacktestResult


def run_research(
    markets: dict[str, pd.DataFrame],
    *,
    instruments: tuple[str, ...] | None = None,
    config: BacktestConfig | None = None,
) -> ResearchRun:
    requested = instruments or tuple(item.symbol for item in DEFAULT_UNIVERSE)
    available = tuple(symbol for symbol in requested if symbol in markets)
    missing = tuple(symbol for symbol in requested if symbol not in markets)

    selected = {symbol: markets[symbol] for symbol in available}
    result = run_multi_market_backtest(selected, config=config)
    return ResearchRun(requested, available, missing, result)


def research_frame(run: ResearchRun) -> pd.DataFrame:
    frame = run.backtest.as_records()
    return pd.DataFrame(frame).sort_values("instrument").reset_index(drop=True)


def research_result(result: BacktestResult) -> dict:
    return {
        "trades": len(result.trades),
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": result.win_rate_pct,
        "profit_factor": result.profit_factor,
        "return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
    }
