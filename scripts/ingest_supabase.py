from __future__ import annotations

import argparse
from datetime import datetime, timezone

from orion_trading.data_quality import validate_candles
from orion_trading.historical_dataset import _frame_hash, _normalise
from orion_trading.provider_factory import provider_from_env
from orion_trading.supabase_market_store import SupabaseMarketDataStore


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest historical ORION market data into Supabase."
    )
    parser.add_argument("--instruments", nargs="+", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument(
        "--timeframes",
        nargs="+",
        default=["D1", "H4", "H1", "M15"],
    )
    args = parser.parse_args()

    start = parse_utc(args.start)
    end = parse_utc(args.end)
    if start >= end:
        raise ValueError("--start must be earlier than --end")

    provider_name = __import__("os").getenv("ORION_DATA_PROVIDER", "oanda")
    provider = provider_from_env()
    store = SupabaseMarketDataStore()

    try:
        for instrument in args.instruments:
            for timeframe in args.timeframes:
                timeframe = timeframe.upper()
                frame = _normalise(
                    provider.candles(instrument, timeframe, start, end)
                )
                if frame.empty:
                    raise ValueError(
                        f"No historical data returned for {instrument}/{timeframe}"
                    )

                report = validate_candles(frame, timeframe)
                if not report.passed:
                    raise ValueError(
                        f"Data quality failed for {instrument}/{timeframe}: {report}"
                    )

                count = store.save(
                    instrument,
                    timeframe,
                    frame,
                    provider_name,
                )
                store.record_dataset(
                    provider=provider_name,
                    instrument=instrument,
                    timeframe=timeframe,
                    start_at=frame.index.min().isoformat(),
                    end_at=frame.index.max().isoformat(),
                    row_count=count,
                    missing_bars=report.missing_bars,
                    sha256=_frame_hash(frame),
                    quality_passed=report.passed,
                )
                print(
                    f"INGESTED {instrument}/{timeframe}: "
                    f"{count} rows, missing gaps={report.missing_bars}"
                )
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()


if __name__ == "__main__":
    main()
