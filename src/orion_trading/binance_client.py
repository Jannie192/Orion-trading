from __future__ import annotations

from datetime import datetime, timezone
import time

import pandas as pd
import requests

from .market_data import MarketDataAdapter


TIMEFRAME_MAP = {
    "M15": "15m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
}

COLUMNS = ("open", "high", "low", "close", "volume")


class BinanceClient:
    """Public Binance spot historical OHLCV adapter.

    This adapter is market-data only: no API key or trading credentials are used.
    Symbols are passed through in Binance format, e.g. BTCUSDT.
    """

    def __init__(
        self,
        base_url: str = "https://data-api.binance.vision",
        session: requests.Session | None = None,
        timeout: float = 10.0,
        page_limit: int = 1000,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.page_limit = min(max(page_limit, 1), 1000)
        self.retry_count = max(retry_count, 0)
        self.retry_delay = max(retry_delay, 0.0)

    @staticmethod
    def _timestamp_ms(value: datetime) -> int:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)

    @staticmethod
    def _interval_ms(timeframe: str) -> int:
        return {
            "M15": 15 * 60 * 1000,
            "H1": 60 * 60 * 1000,
            "H4": 4 * 60 * 60 * 1000,
            "D1": 24 * 60 * 60 * 1000,
        }[timeframe]

    def _get(self, params: dict) -> list:
        url = f"{self.base_url}/api/v3/klines"
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code in (418, 429, 500, 502, 503, 504):
                    if attempt < self.retry_count:
                        retry_after = response.headers.get("Retry-After")
                        delay = float(retry_after) if retry_after else self.retry_delay * (2**attempt)
                        time.sleep(delay)
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise ValueError(f"Unexpected Binance response: {payload!r}")
                return payload
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    time.sleep(self.retry_delay * (2**attempt))
                    continue
                raise RuntimeError(f"Binance market-data request failed: {exc}") from exc
        raise RuntimeError(f"Binance market-data request failed: {last_error}")

    def candles(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        timeframe = timeframe.upper()
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported Binance timeframe: {timeframe!r}")
        if start >= end:
            raise ValueError("start must be earlier than end")

        start_ms = self._timestamp_ms(start)
        end_ms = self._timestamp_ms(end)
        interval_ms = self._interval_ms(timeframe)
        rows: list[list] = []
        cursor = start_ms

        while cursor <= end_ms:
            batch = self._get({
                "symbol": instrument.upper(),
                "interval": TIMEFRAME_MAP[timeframe],
                "startTime": cursor,
                "endTime": end_ms,
                "limit": self.page_limit,
            })
            if not batch:
                break
            rows.extend(batch)
            last_open = int(batch[-1][0])
            next_cursor = last_open + interval_ms
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(batch) < self.page_limit:
                break

        if not rows:
            return pd.DataFrame(columns=COLUMNS, index=pd.DatetimeIndex([], tz="UTC"))

        frame = pd.DataFrame(
            [[row[1], row[2], row[3], row[4], row[5], row[0]] for row in rows],
            columns=[*COLUMNS, "open_time_ms"],
        )
        frame["open_time_ms"] = pd.to_datetime(frame["open_time_ms"], unit="ms", utc=True)
        frame = frame.set_index("open_time_ms")
        for column in COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        frame = frame.loc[(frame.index >= pd.Timestamp(start, tz="UTC") if start.tzinfo is None else frame.index >= pd.Timestamp(start).tz_convert("UTC"))]
        end_ts = pd.Timestamp(end)
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        else:
            end_ts = end_ts.tz_convert("UTC")
        frame = frame.loc[frame.index <= end_ts]
        return frame
