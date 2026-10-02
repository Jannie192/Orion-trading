from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from orion_trading.backtest_oafs import run_oafs_backtest
from orion_trading.data_store import CsvDataStore
from orion_trading.ingestion import ingest
from orion_trading.provider_factory import provider_from_env
from orion_trading.validation_report import build_validation_report, write_validation_report
from orion_trading.walk_forward import run_walk_forward

INSTRUMENTS = ["EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD"]
TIMEFRAMES = ("D1", "H4", "H1", "M15")

def _utc(value: str):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)

def main():
    parser = argparse.ArgumentParser(description="Run OAFS research and build the validation report.")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", default="reports/validation")
    parser.add_argument("--simulations", type=int, default=10000)
    args = parser.parse_args()

    start, end = _utc(args.start), _utc(args.end)
    provider = provider_from_env()
    results = []

    try:
        for instrument in INSTRUMENTS:
            ingest(provider, instrument, start, end)
            store = CsvDataStore()
            frames = {tf: store.load(instrument, tf) for tf in TIMEFRAMES}
            results.append(run_oafs_backtest(frames, instrument))
    finally:
        close = getattr(provider, "close", None)
        if close:
            close()

    wf = run_walk_forward({i: {tf: CsvDataStore().load(i, tf) for tf in TIMEFRAMES} for i in INSTRUMENTS}, INSTRUMENTS, start, end)
    report = build_validation_report(results, start, end, simulations=args.simulations, walk_forward=wf)
    path = write_validation_report(report, args.output)
    print(json.dumps(report["portfolio"], indent=2))
    print(f"Validation report: {path}")

if __name__ == "__main__":
    main()
