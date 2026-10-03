from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Protocol

from .backtest import BacktestResult, Backtester
from .dataset_manager import DatasetManager


@dataclass(frozen=True)
class ResearchResult:
    instrument: str
    timeframe: str
    data_rows: int
    data_downloaded: int
    gaps_filled: int
    backtest: BacktestResult
    run_id: str | None = None


class ResearchResultStore(Protocol):
    def record_research_result(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
        result: ResearchResult,
        start_at: str,
        end_at: str,
    ) -> str:
        ...


class ResearchCycle:
    """Prepare persistent data, run the causal backtester, and optionally persist results."""

    def __init__(
        self,
        dataset_manager: DatasetManager,
        backtester: Backtester | None = None,
        result_store: ResearchResultStore | None = None,
        strategy_name: str = "ORION",
        strategy_version: str = "1.0",
    ) -> None:
        self.dataset_manager = dataset_manager
        self.backtester = backtester or Backtester()
        self.result_store = result_store
        self.strategy_name = strategy_name
        self.strategy_version = strategy_version

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
                start_at = sync.requested_start.astimezone(timezone.utc).isoformat()
                end_at = sync.requested_end.astimezone(timezone.utc).isoformat()
                backtest = self.backtester.run_from_store(
                    self.dataset_manager.store,
                    instrument=instrument,
                    timeframe=timeframe,
                    start_at=start_at,
                    end_at=end_at,
                )
                result = ResearchResult(
                    instrument=instrument,
                    timeframe=timeframe,
                    data_rows=sync.final_rows,
                    data_downloaded=sync.downloaded_rows,
                    gaps_filled=sync.gaps_filled,
                    backtest=backtest,
                )
                if self.result_store is not None:
                    run_id = self.result_store.record_research_result(
                        strategy_name=self.strategy_name,
                        strategy_version=self.strategy_version,
                        result=result,
                        start_at=start_at,
                        end_at=end_at,
                    )
                    result = ResearchResult(
                        instrument=result.instrument,
                        timeframe=result.timeframe,
                        data_rows=result.data_rows,
                        data_downloaded=result.data_downloaded,
                        gaps_filled=result.gaps_filled,
                        backtest=result.backtest,
                        run_id=run_id,
                    )
                results.append(result)
        return tuple(results)
