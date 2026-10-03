from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import requests


_TIMEFRAME_MAP = {
    "M15": "15m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
}
_STEP = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}


class BiquoteFXProvider:
    """Broker-neutral FX OHLC provider using Biquote's public no-key endpoint."""

    BASE_URL = "https://biquote.io/api"

    def __init__(self, timeout: int = 30, page_limit: int = 1000) -> None:
        self.timeout = timeout
        self.page_limit = min(max(page_limit, 1), 1000)

    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        timeframe = timeframe.upper()
        interval = _TIMEFRAME_MAP.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)
        cursor = start
        frames: list[pd.DataFrame] = []

        while cursor < end:
            response = requests.get(
                f"{self.BASE_URL}/{instrument.upper()}/ohlc",
                params={
                    "interval": interval,
                    "limit": self.page_limit,
                    "from": cursor.isoformat().replace("+00:00", "Z"),
                    "to": end.isoformat().replace("+00:00", "Z"),
                },
                timeout=self.timeout,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Biquote request failed ({response.status_code}): {response.text[:500]}"
                )
            payload = response.json()
            bars = payload.get("bars") or []
            if not bars:
                break

            frame = pd.DataFrame(bars)
            timestamp_column = "openTime" if "openTime" in frame else "timestamp"
            frame[timestamp_column] = pd.to_datetime(frame[timestamp_column], utc=True)
            frame = frame.set_index(timestamp_column).sort_index()
            frame = frame[(frame.index >= cursor) & (frame.index < end)]
            if frame.empty:
                break

            for column in ("open", "high", "low", "close"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame["volume"] = pd.to_numeric(frame.get("volume", 0.0), errors="coerce").fillna(0.0)
            frames.append(frame[["open", "high", "low", "close", "volume"]].dropna())

            last = frame.index[-1].to_pydatetime()
            next_cursor = last + timedelta(minutes=_STEP[timeframe])
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            if len(frame) < self.page_limit:
                break

        if not frames:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        result = pd.concat(frames).sort_index()
        return result[~result.index.duplicated(keep="last")]
