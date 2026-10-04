from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import requests


_YAHOO_SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "USDCHF": "CHF=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "NZDUSD": "NZDUSD=X",
}

_TIMEFRAME_INTERVAL = {"H1": "1h", "D1": "1d"}


class YahooFXProvider:
    """Free, no-key Yahoo Finance historical FX provider for research/backtesting.

    H4 is built causally from H1 bars. M15 is intentionally unsupported here because
    Yahoo's intraday retention is limited; the research bootstrap currently uses H1/H4/D1.
    """

    BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    def _fetch(self, yahoo_symbol: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
        response = requests.get(
            f"{self.BASE_URL}/{yahoo_symbol}",
            params={
                "period1": int(start.timestamp()),
                "period2": int(end.timestamp()),
                "interval": interval,
                "events": "history",
                "includeAdjustedClose": "true",
            },
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if not response.ok:
            raise RuntimeError(f"Yahoo Finance request failed ({response.status_code}): {response.text[:500]}")
        payload = response.json()
        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            error = (payload.get("chart") or {}).get("error")
            raise RuntimeError(f"Yahoo Finance returned no data: {error}")
        node = result[0]
        timestamps = node.get("timestamp") or []
        quote = ((node.get("indicators") or {}).get("quote") or [{}])[0]
        if not timestamps:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        frame = pd.DataFrame({
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", []),
        }, index=pd.to_datetime(timestamps, unit="s", utc=True))
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame.dropna(subset=["open", "high", "low", "close"])

    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        instrument = instrument.upper()
        timeframe = timeframe.upper()
        yahoo_symbol = _YAHOO_SYMBOLS.get(instrument)
        if not yahoo_symbol:
            raise ValueError(f"Unsupported FX instrument: {instrument}")
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        if timeframe == "H4":
            hourly = self._fetch(yahoo_symbol, "1h", start, end)
            if hourly.empty:
                return hourly
            # Preserve OHLC semantics while aggregating four hourly bars from UTC boundaries.
            frame = hourly.resample("4h", label="left", closed="left").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }).dropna(subset=["open", "high", "low", "close"])
            return frame[(frame.index >= start) & (frame.index < end)]

        interval = _TIMEFRAME_INTERVAL.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return self._fetch(yahoo_symbol, interval, start, end)


# Backward-compatible alias for existing imports while the repository transitions.
BiquoteFXProvider = YahooFXProvider
