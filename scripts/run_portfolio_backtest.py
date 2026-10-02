from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from orion_trading.provider_factory import provider_from_env
from orion_trading.ingestion import ingest
from orion_trading.portfolio_backtest import summarize_portfolio
from orion_trading.backtest_oafs import run_oafs_backtest

INSTRUMENTS=["EUR_USD","GBP_USD","USD_JPY","USD_CHF","AUD_USD","USD_CAD","NZD_USD"]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    p.add_argument("--output",default="reports/portfolio")
    args=p.parse_args()
    start=datetime.fromisoformat(args.start.replace("Z","+00:00")).astimezone(timezone.utc)
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(timezone.utc)
    provider=provider_from_env()
    results=[]
    try:
        for instrument in INSTRUMENTS:
            ingest(provider,instrument,start,end)
            from orion_trading.data_store import CsvDataStore
            store=CsvDataStore()
            frames={tf:store.load(instrument,tf) for tf in ("D1","H4","H1","M15")}
            results.append(run_oafs_backtest(frames,instrument))
    finally:
        close=getattr(provider,"close",None)
        if close: close()
    summary=summarize_portfolio(results)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    (out/"summary.json").write_text(json.dumps(summary.__dict__,indent=2))
    print(json.dumps(summary.__dict__,indent=2))

if __name__=="__main__":
    main()
