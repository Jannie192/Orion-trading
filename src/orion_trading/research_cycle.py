from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .backtest import BacktestConfig, BacktestResult, Backtester
from .dataset_manager import DatasetManager


@dataclass(frozen=True)
class ResearchResult:
    instrument: str
    timeframe: str
    data_rows: int
    data_downloaded: int
    gaps_filled: int
    backtest: BacktestResult


class ResearchCycle:
    """Prepare persistent data and immediately run the existing causal backtester."""

    def __init__(
        self,
        dataset_manager: DatasetManager,
        backtester: Backtester | None = None,
    ) -> None:
        self.dataset_manager = dataset_manager
        self.backtester = backtester or Backtester()

    def run(
        self,
        instruments: Iterable[str],
        timeframes: Iterable[str],
        start: datetime,
        end: datetime,
    ) -> tuple[ResearchResult, ...]:
        results: list[ResearchResult] = []
        for instrument in instruments:
            for timeframe in timeframes:
                sync = self.dataset_manager.sync(instrument, timeframe, start, end)
                backtest = self.backtester.run_from_store(
                    self.dataset_manager.store,
                    instrument=instrument,
                    timeframe=timeframe,
                    start_at=start.astimezone().isoformat(),
                    end_at=end.astimezone().isoformat(),
                )
                results.append(
                    ResearchResult(
                        instrument=instrument,
                        timeframe=timeframe,
                        data_rows=sync.final_rows,
                        data_downloaded=sync.downloaded_rows,
                        gaps_filled=sync.gaps_filled,
                        backtest=backtest,
                    )
                )
        return tuple(results)
