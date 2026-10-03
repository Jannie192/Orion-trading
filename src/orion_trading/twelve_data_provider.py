from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import requests


_TIMEFRAME_MAP = {
    "M15": "15min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1day",
}


class TwelveDataFXProvider:
    """Broker-neutral FX OHLC provider backed by Twelve Data."""

    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key or os.getenv("TWELVEDATA_API_KEY", "")
        if not self.api_key:
            raise ValueError("TWELVEDATA_API_KEY is required")
        self.timeout = timeout

    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        timeframe = timeframe.upper()
        interval = _TIMEFRAME_MAP.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        symbol = instrument.upper()
        if len(symbol) == 6 and "/" not in symbol:
            symbol = f"{symbol[:3]}/{symbol[3:]}"

        response = requests.get(
            self.BASE_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "start_date": start.astimezone().isoformat(),
                "end_date": end.astimezone().isoformat(),
                "order": "ASC",
                "outputsize": 5000,
                "apikey": self.api_key,
            },
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(f"Twelve Data request failed ({response.status_code}): {response.text[:500]}")
        payload = response.json()
        if payload.get("status") == "error":
            raise RuntimeError(f"Twelve Data error: {payload.get('message', 'unknown error')}")
        values = payload.get("values") or []
        if not values:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        frame = pd.DataFrame(values)
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        frame = frame.set_index("datetime").sort_index()
        for column in ("open", "high", "low", "close"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if "volume" not in frame:
            frame["volume"] = 0.0
        else:
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
        return frame[["open", "high", "low", "close", "volume"]].dropna()
