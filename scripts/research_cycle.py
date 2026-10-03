from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta
import os

from orion_trading.dataset_manager import DatasetManager
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
    args = parser.parse_args()

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.lookback_days)
    provider_name = os.getenv("ORION_DATA_PROVIDER", "oanda")
    provider = provider_from_env()
    store = SupabaseMarketDataStore()
    manager = DatasetManager(store, provider, provider_name)

    failures = []
    try:
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
