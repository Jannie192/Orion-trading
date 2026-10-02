from __future__ import annotations

import argparse
from datetime import datetime, timezone

from orion_trading.ingestion import ingest
from orion_trading.provider_factory import provider_from_env

def main():
    p=argparse.ArgumentParser(description="Ingest ORION historical FX data.")
    p.add_argument("--instrument",required=True)
    p.add_argument("--start",required=True)
    p.add_argument("--end",required=True)
    args=p.parse_args()
    start=datetime.fromisoformat(args.start.replace("Z","+00:00")).astimezone(timezone.utc)
    end=datetime.fromisoformat(args.end.replace("Z","+00:00")).astimezone(timezone.utc)
    provider=provider_from_env()
    try:
        for result in ingest(provider,args.instrument,start,end):
            print(result)
    finally:
        close=getattr(provider,"close",None)
        if close:
            close()

if __name__=="__main__":
    main()
