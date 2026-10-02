from __future__ import annotations

from datetime import datetime
import os

import pandas as pd

from .oanda_client import OandaClient, OandaConfig
from .regime import classify_regime
from .signals import detect

INSTRUMENTS = ("EUR_USD", "GBP_USD", "USD_JPY", "USD_CHF", "AUD_USD", "USD_CAD", "NZD_USD")
GRANULARITIES = ("D", "H4", "H1", "M15")


def client_from_env() -> OandaClient:
    token = os.environ.get("OANDA_API_TOKEN", "")
    account = os.environ.get("OANDA_ACCOUNT_ID", "")
    practice = os.environ.get("OANDA_PRACTICE", "true").lower() != "false"
    if not token or not account:
        raise RuntimeError("OANDA_API_TOKEN and OANDA_ACCOUNT_ID are required")
    return OandaClient(OandaConfig(account_id=account, token=token, practice=practice))


def candles_frame(payload: dict) -> pd.DataFrame:
    rows = []
    for candle in payload.get("candles", []):
        if not candle.get("complete", False):
            continue
        mid = candle.get("mid") or candle.get("bid") or candle.get("ask")
        if not mid:
            continue
        rows.append({"time": pd.Timestamp(candle["time"]), "open": float(mid["o"]), "high": float(mid["h"]), "low": float(mid["l"]), "close": float(mid["c"]), "volume": int(candle.get("volume", 0))})
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return pd.DataFrame(rows).set_index("time").sort_index()


def scan_once(client: OandaClient, instrument: str, granularity: str = "M15", count: int = 500):
    frame = candles_frame(client.candles(instrument, granularity, count))
    if frame.empty:
        return []
    regime = classify_regime(frame)
    return detect(frame, regime)
