from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone, timedelta

from orion_trading.dataset_manager import DatasetManager
from orion_trading.provider_factory import provider_from_env
from orion_trading.supabase_market_store import SupabaseMarketDataStore


DEFAULT_INSTRUMENTS = (
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
    "AUDUSD", "USDCAD", "NZDUSD",
)
DEFAULT_TIMEFRAMES = ("D1", "H4", "H1", "M15")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize ORION historical market data into Supabase."
    )
    parser.add_argument("--instruments", nargs="+", default=list(DEFAULT_INSTRUMENTS))
    parser.add_argument("--timeframes", nargs="+", default=list(DEFAULT_TIMEFRAMES))
    parser.add_argument("--start", type=parse_utc)
    parser.add_argument("--end", type=parse_utc)
    parser.add_argument("--lookback-days", type=int, default=365)
    args = parser.parse_args()

    end = args.end or datetime.now(timezone.utc)
    start = args.start or (end - timedelta(days=args.lookback_days))
    if start >= end:
        raise ValueError("--start must be earlier than --end")

    provider_name = os.getenv("ORION_DATA_PROVIDER", "oanda")
    provider = provider_from_env()
    store = SupabaseMarketDataStore()
    manager = DatasetManager(store, provider, provider_name)

    try:
        for instrument in args.instruments:
            for timeframe in args.timeframes:
                result = manager.sync(instrument, timeframe, start, end)
                print(
                    f"SYNCED {instrument}/{timeframe}: "
                    f"existing={result.existing_rows} "
                    f"downloaded={result.downloaded_rows} "
                    f"gaps={result.gaps_filled} "
                    f"final={result.final_rows}"
                )
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()


if __name__ == "__main__":
    main()
