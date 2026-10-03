from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Protocol

from .backtest import BacktestResult, Backtester
from .dataset_manager import DatasetManager
from .experiment_validation import ExperimentValidationConfig, validate_experiment
from .strategy_experiments import StrategyExperimentResult, StrategyExperimenter


@dataclass(frozen=True)
class ResearchResult:
    instrument: str
    timeframe: str
    data_rows: int
    data_downloaded: int
    gaps_filled: int
    backtest: BacktestResult
    run_id: str | None = None
    approval_status: str | None = None
    paper_candidate_id: str | None = None


class ResearchExperimentStore(Protocol):
    def record_strategy_experiment(
        self, *, experiment: StrategyExperimentResult, days: int = 0, validation: dict | None = None
    ) -> str: ...

    def promote_paper_candidate(
        self, *, experiment: StrategyExperimentResult, experiment_id: str,
        validation: dict, days: int = 0
    ) -> str: ...


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
        experimenter: StrategyExperimenter | None = None,
        experiment_store: ResearchExperimentStore | None = None,
        experiment_grids: Mapping[str, Mapping[str, Iterable[float]]] | None = None,
        validation_config: ExperimentValidationConfig | None = None,
    ) -> None:
        self.dataset_manager = dataset_manager
        self.backtester = backtester or Backtester()
        self.result_store = result_store
        self.strategy_name = strategy_name
        self.strategy_version = strategy_version
        self.experimenter = experimenter
        self.experiment_store = experiment_store
        self.experiment_grids = experiment_grids or {}
        self.validation_config = validation_config or ExperimentValidationConfig()

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
                if self.experimenter is not None:
                    grid = self.experiment_grids.get(instrument) or self.experiment_grids.get("*")
                    if grid:
                        candles = self.dataset_manager.store.load(
                            instrument, timeframe, start_at=start_at, end_at=end_at
                        )
                        experiment = self.experimenter.run(
                            candles,
                            instrument=instrument,
                            timeframe=timeframe,
                            parameter_grid=grid,
                            strategy_name=self.strategy_name,
                            strategy_version=f"{self.strategy_version}-experiment",
                        )
                        validation = validate_experiment(
                            candles,
                            experiment,
                            start=sync.requested_start,
                            end=sync.requested_end,
                            config=self.validation_config,
                        )
                        experiment_id = None
                        paper_candidate_id = None
                        approval_status = (validation.get("approval") or {}).get("status")
                        if self.experiment_store is not None:
                            experiment_id = self.experiment_store.record_strategy_experiment(
                                experiment=experiment,
                                days=max((sync.requested_end - sync.requested_start).days, 0),
                                validation=validation,
                            )
                            if approval_status == "PASS":
                                paper_candidate_id = self.experiment_store.promote_paper_candidate(
                                    experiment=experiment,
                                    experiment_id=experiment_id,
                                    validation=validation,
                                    days=max((sync.requested_end - sync.requested_start).days, 0),
                                )
                        result = ResearchResult(
                            instrument=result.instrument,
                            timeframe=result.timeframe,
                            data_rows=result.data_rows,
                            data_downloaded=result.data_downloaded,
                            gaps_filled=result.gaps_filled,
                            backtest=result.backtest,
                            run_id=result.run_id,
                            approval_status=approval_status,
                            paper_candidate_id=paper_candidate_id,
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
                        approval_status=result.approval_status,
                        paper_candidate_id=result.paper_candidate_id,
                    )
                results.append(result)
        return tuple(results)
