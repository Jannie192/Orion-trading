from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Iterable, Mapping

import pandas as pd

from .backtest import BacktestConfig, BacktestResult, Backtester
from .trading_engine import TradingEngine, TradingEngineConfig


@dataclass(frozen=True)
class StrategyVariant:
    """One concrete parameter combination evaluated by an experiment."""

    parameters: dict[str, float]
    result: BacktestResult
    score: float
    rank: int = 0


@dataclass(frozen=True)
class StrategyExperimentResult:
    """Deterministic result of evaluating a parameter grid."""

    strategy_name: str
    strategy_version: str
    instrument: str
    timeframe: str
    variants: tuple[StrategyVariant, ...]
    best: StrategyVariant | None

    @property
    def variant_count(self) -> int:
        return len(self.variants)


class StrategyExperimenter:
    """Run controlled parameter experiments against the existing causal backtester.

    The experimenter deliberately varies only TradingEngineConfig values. It does
    not alter signal logic or market data, so every candidate remains comparable
    under the same backtesting semantics.
    """

    SUPPORTED_PARAMETERS = frozenset(
        {"risk_per_trade_pct", "atr_stop_multiple", "reward_multiple", "min_signal_score"}
    )

    def __init__(
        self,
        *,
        backtest_config: BacktestConfig | None = None,
        max_variants: int = 100,
    ) -> None:
        if max_variants <= 0:
            raise ValueError("max_variants must be positive")
        self.backtest_config = backtest_config or BacktestConfig()
        self.max_variants = max_variants

    def run(
        self,
        candles: pd.DataFrame,
        *,
        instrument: str,
        timeframe: str,
        parameter_grid: Mapping[str, Iterable[float]],
        strategy_name: str = "ORION",
        strategy_version: str = "experiment",
    ) -> StrategyExperimentResult:
        grid = self._normalise_grid(parameter_grid)
        combinations = list(product(*(grid[name] for name in grid)))
        if len(combinations) > self.max_variants:
            raise ValueError(
                f"parameter grid creates {len(combinations)} variants; "
                f"max_variants is {self.max_variants}"
            )

        variants: list[StrategyVariant] = []
        for values in combinations:
            parameters = dict(zip(grid.keys(), values))
            config = TradingEngineConfig(**parameters)
            engine = TradingEngine(config=config)
            result = Backtester(engine=engine, config=self.backtest_config).run(
                candles, instrument=instrument
            )
            variants.append(
                StrategyVariant(
                    parameters=parameters,
                    result=result,
                    score=self.score(result),
                )
            )

        ordered = sorted(
            variants,
            key=lambda item: (
                item.score,
                item.result.total_return_pct,
                -item.result.max_drawdown_pct,
                item.result.trade_count if hasattr(item.result, "trade_count") else len(item.result.trades),
            ),
            reverse=True,
        )
        ranked = tuple(
            StrategyVariant(
                parameters=item.parameters,
                result=item.result,
                score=item.score,
                rank=index,
            )
            for index, item in enumerate(ordered, start=1)
        )
        return StrategyExperimentResult(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            instrument=instrument,
            timeframe=timeframe.upper(),
            variants=ranked,
            best=ranked[0] if ranked else None,
        )

    @staticmethod
    def score(result: BacktestResult) -> float:
        """Transparent research score: return adjusted for drawdown and sample size.

        The score is not a trading guarantee. It is only a deterministic ordering
        mechanism for deciding which variants should proceed to deeper validation.
        """
        if not result.trades:
            return float("-inf")
        drawdown = max(result.max_drawdown_pct, 0.01)
        sample_factor = min(len(result.trades) / 20.0, 1.0)
        return (result.total_return_pct / drawdown) * sample_factor

    @classmethod
    def _normalise_grid(
        cls, parameter_grid: Mapping[str, Iterable[float]]
    ) -> dict[str, tuple[float, ...]]:
        if not parameter_grid:
            raise ValueError("parameter_grid must contain at least one parameter")

        normalised: dict[str, tuple[float, ...]] = {}
        for name, values in parameter_grid.items():
            if name not in cls.SUPPORTED_PARAMETERS:
                raise ValueError(f"unsupported strategy parameter: {name}")
            parsed = tuple(float(value) for value in values)
            if not parsed:
                raise ValueError(f"parameter grid is empty for {name}")
            if any(value <= 0 for value in parsed if name != "min_signal_score"):
                raise ValueError(f"{name} values must be positive")
            normalised[name] = parsed
        return normalised


def serialise_experiment(result: StrategyExperimentResult) -> dict[str, Any]:
    """Convert an experiment result into JSON-compatible research metadata."""

    def variant_payload(variant: StrategyVariant) -> dict[str, Any]:
        bt = variant.result
        return {
            "rank": variant.rank,
            "parameters": variant.parameters,
            "score": variant.score,
            "initial_equity": bt.initial_equity,
            "final_equity": bt.final_equity,
            "total_return_pct": bt.total_return_pct,
            "max_drawdown_pct": bt.max_drawdown_pct,
            "trade_count": len(bt.trades),
            "wins": bt.wins,
            "losses": bt.losses,
            "win_rate_pct": bt.win_rate_pct,
            "profit_factor": None if bt.profit_factor == float("inf") else bt.profit_factor,
            "profit_factor_infinite": bt.profit_factor == float("inf"),
        }

    return {
        "strategy_name": result.strategy_name,
        "strategy_version": result.strategy_version,
        "instrument": result.instrument,
        "timeframe": result.timeframe,
        "variant_count": result.variant_count,
        "best": variant_payload(result.best) if result.best else None,
        "variants": [variant_payload(variant) for variant in result.variants],
    }
