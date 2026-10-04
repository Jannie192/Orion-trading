from __future__ import annotations

import lzma
import struct
import time
from datetime import datetime, timezone

import pandas as pd
import requests


_DUKA_SYMBOLS = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "USDJPY": "USDJPY",
    "USDCHF": "USDCHF",
    "AUDUSD": "AUDUSD",
    "USDCAD": "USDCAD",
    "NZDUSD": "NZDUSD",
}


class DukascopyFXProvider:
    """Dukascopy Bank historical FX OHLC provider.

    Uses Dukascopy's public historical .bi5 candle files. H1 and D1 are native
    historical feeds; H4 is resampled causally from H1. No API key is required.
    """

    BASE_URL = "https://datafeed.dukascopy.com/datafeed"

    def __init__(self, timeout: int = 30, retries: int = 6) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ORION-trading-research/1.0"})

    @staticmethod
    def _scale(instrument: str) -> float:
        return 1000.0 if instrument.endswith("JPY") else 100000.0

    def _get(self, url: str) -> bytes | None:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 404:
                    return None
                if response.status_code in {429, 500, 502, 503, 504}:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(2.0 ** attempt, 20.0)
                    time.sleep(delay)
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                    continue
                response.raise_for_status()
                return response.content
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(min(2.0 ** attempt, 20.0))
        raise RuntimeError(f"Dukascopy request failed after {self.retries} attempts: {last_error}")

    def _decode_ohlc(self, payload: bytes, instrument: str, period_start: datetime) -> pd.DataFrame:
        if not payload:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        try:
            raw = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
        except lzma.LZMAError as exc:
            raise RuntimeError(f"Unable to decode Dukascopy .bi5 data: {exc}") from exc
        record_size = 24
        usable = len(raw) - (len(raw) % record_size)
        scale = self._scale(instrument)
        rows = []
        for offset in range(0, usable, record_size):
            seconds, open_raw, close_raw, low_raw, high_raw, volume = struct.unpack(
                ">IIIII f", raw[offset:offset + record_size]
            )
            ts = period_start + pd.to_timedelta(seconds, unit="s").to_pytimedelta()
            rows.append((ts, open_raw / scale, high_raw / scale, low_raw / scale, close_raw / scale, float(volume)))
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
        frame.index = pd.DatetimeIndex(frame.index, tz="UTC")
        return frame.sort_index()

    def _fetch_h1_month(self, instrument: str, year: int, month: int) -> pd.DataFrame:
        symbol = _DUKA_SYMBOLS[instrument]
        url = f"{self.BASE_URL}/{symbol}/{year}/{month - 1:02d}/BID_candles_hour_1.bi5"
        payload = self._get(url)
        if payload is None:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        return self._decode_ohlc(payload, instrument, datetime(year, month, 1, tzinfo=timezone.utc))

    def _fetch_d1_year(self, instrument: str, year: int) -> pd.DataFrame:
        symbol = _DUKA_SYMBOLS[instrument]
        url = f"{self.BASE_URL}/{symbol}/{year}/BID_candles_day_1.bi5"
        payload = self._get(url)
        if payload is None:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        return self._decode_ohlc(payload, instrument, datetime(year, 1, 1, tzinfo=timezone.utc))

    @staticmethod
    def _concat_nonempty(frames: list[pd.DataFrame]) -> pd.DataFrame:
        nonempty = [frame for frame in frames if not frame.empty]
        if not nonempty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        return pd.concat(nonempty)

    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        instrument = instrument.upper()
        timeframe = timeframe.upper()
        if instrument not in _DUKA_SYMBOLS:
            raise ValueError(f"Unsupported FX instrument: {instrument}")
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        if timeframe in {"H1", "H4"}:
            months = pd.period_range(
                start=start.date().replace(day=1),
                end=end.date().replace(day=1),
                freq="M",
            )
            frames = [self._fetch_h1_month(instrument, p.year, p.month) for p in months]
            frame = self._concat_nonempty(frames)
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            if timeframe == "H4":
                frame = (
                    frame.resample("4h", label="left", closed="left")
                    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                    .dropna(subset=["open", "high", "low", "close"])
                )
            return frame[(frame.index >= start) & (frame.index < end)]

        if timeframe == "D1":
            frames = [self._fetch_d1_year(instrument, year) for year in range(start.year, end.year + 1)]
            frame = self._concat_nonempty(frames)
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            return frame[(frame.index >= start) & (frame.index < end)]

        raise ValueError(f"Unsupported timeframe: {timeframe}. Use H1, H4, or D1.")


DukascopyProvider = DukascopyFXProvider
YahooFXProvider = DukascopyFXProvider
BiquoteFXProvider = DukascopyFXProvider
