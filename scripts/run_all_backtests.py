from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import json

from orion_trading.history import fetch_multi_timeframe_history
from orion_trading.oanda_client import OandaClient
from orion_trading.backtest_oafs import run_oafs_backtest

INSTRUMENTS = ["EUR_USD","GBP_USD","USD_JPY","USD_CHF","AUD_USD","USD_CAD","NZD_USD"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--output",default="reports/oafs")
    args=p.parse_args()
    start=datetime.fromisoformat(args.start.replace("Z","+00:00")).astimezone(timezone.utc)
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(timezone.utc)
    client=OandaClient.from_env()
    root=Path(args.output); root.mkdir(parents=True,exist_ok=True)
    combined=[]
    for instrument in INSTRUMENTS:
        print(f"Downloading {instrument}...")
        frames=fetch_multi_timeframe_history(client,instrument,start,end)
        result=run_oafs_backtest(frames,instrument)
        summary={k:v for k,v in result.items() if k not in {"trade_log","rejections"}}
        (root/f"{instrument}.json").write_text(json.dumps(result,indent=2,default=str))
        combined.append(summary)
        print(json.dumps(summary,indent=2,default=str))
    (root/"combined.json").write_text(json.dumps(combined,indent=2,default=str))

if __name__=="__main__":
    main()
