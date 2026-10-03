from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import os

from orion_trading.dataset_manager import DatasetManager
from orion_trading.research_cycle import ResearchCycle
from orion_trading.strategy_experiments import StrategyExperimenter
from orion_trading.provider_factory import provider_from_env
from orion_trading.supabase_market_store import SupabaseMarketDataStore

DEFAULT_INSTRUMENTS = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "USDCAD", "NZDUSD",
)
DEFAULT_TIMEFRAMES = ("D1", "H4", "H1", "M15")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ORION autonomous data/research preparation cycle.")
    parser.add_argument("--instruments", nargs="+", default=list(DEFAULT_INSTRUMENTS))
    parser.add_argument("--timeframes", nargs="+", default=list(DEFAULT_TIMEFRAMES))
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--run-experiments", action="store_true", help="Run controlled strategy parameter experiments after data sync.")
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.lookback_days)
    provider_name = os.getenv("ORION_DATA_PROVIDER", "oanda")
    provider = provider_from_env()
    store = SupabaseMarketDataStore()
    manager = DatasetManager(store, provider, provider_name)

    failures = []
    try:
        if args.run_experiments:
            experimenter = StrategyExperimenter(max_variants=18)
            experiment_grids = {
                "*": {
                    "atr_stop_multiple": (1.0, 1.5, 2.0),
                    "reward_multiple": (1.5, 2.0, 3.0),
                }
            }
            cycle = ResearchCycle(
                manager,
                result_store=store,
                experimenter=experimenter,
                experiment_store=store,
                experiment_grids=experiment_grids,
            )
            try:
                results = cycle.run(args.instruments, args.timeframes, start, end)
                for result in results:
                    print(
                        f"RESEARCH {result.instrument}/{result.timeframe} "
                        f"rows={result.data_rows} "
                        f"baseline_return={result.backtest.total_return_pct:.2f}% "
                        f"trades={len(result.backtest.trades)}"
                    )
            except Exception as exc:
                failures.append(f"research cycle: {exc}")
                print(f"FAILED research cycle: {exc}")
        else:
            for instrument in args.instruments:
                for timeframe in args.timeframes:
                    try:
                        result = manager.sync(instrument, timeframe, start, end)
                        print(
                            f"READY {instrument}/{timeframe} "
                            f"rows={result.final_rows} gaps_filled={result.gaps_filled}"
                        )
                    except Exception as exc:
                        failures.append(f"{instrument}/{timeframe}: {exc}")
                        print(f"FAILED {instrument}/{timeframe}: {exc}")
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    if failures:
        raise SystemExit("\n".join(failures))


if __name__ == "__main__":
    main()
