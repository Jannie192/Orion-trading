from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from orion_trading.history import fetch_multi_timeframe_history
from orion_trading.oanda_client import OandaClient
from orion_trading.backtest_oafs import run_oafs_backtest


def main() -> None:
    p = argparse.ArgumentParser(description="Run an OAFS historical research backtest.")
    p.add_argument("--instrument", default="EUR_USD")
    p.add_argument("--start", required=True, help="UTC ISO timestamp")
    p.add_argument("--end", required=True, help="UTC ISO timestamp")
    p.add_argument("--output", default="reports/oafs")
    args = p.parse_args()

    start = datetime.fromisoformat(args.start.replace("Z", "+00:00")).astimezone(timezone.utc)
    end = datetime.fromisoformat(args.end.replace("Z", "+00:00")).astimezone(timezone.utc)

    client = OandaClient.from_env()
    frames = fetch_multi_timeframe_history(client, args.instrument, start, end)
    result = run_oafs_backtest(frames, args.instrument)

    out = Path(args.output) / args.instrument
    out.mkdir(parents=True, exist_ok=True)

    import json
    (out / "summary.json").write_text(json.dumps({k: v for k, v in result.items() if k not in {"trade_log", "rejections"}}, indent=2, default=str))
    (out / "trades.json").write_text(json.dumps(result["trade_log"], indent=2, default=str))
    (out / "rejections.json").write_text(json.dumps(result["rejections"], indent=2, default=str))

    print(json.dumps({k: v for k, v in result.items() if k not in {"trade_log", "rejections"}}, indent=2, default=str))


if __name__ == "__main__":
    main()
