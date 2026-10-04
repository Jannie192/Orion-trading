from __future__ import annotations

import logging
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

_LOG = logging.getLogger("orion.dukascopy")
_COLUMNS = ["open", "high", "low", "close", "volume"]


class DukascopyFXProvider:
    """Dukascopy historical FX OHLC provider with explicit progress/validation.

    H1 and D1 use native .bi5 candle feeds; H4 is causally resampled from H1.
    Missing weekend/holiday files are normal, but a requested period that
    produces no candles is treated as a hard failure rather than silently
    becoming an empty research dataset.
    """

    BASE_URL = "https://datafeed.dukascopy.com/datafeed"

    def __init__(self, timeout: int = 20, retries: int = 5) -> None:
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "ORION-trading-research/1.0"})

    @staticmethod
    def _empty() -> pd.DataFrame:
        return pd.DataFrame(columns=_COLUMNS)

    @staticmethod
    def _scale(instrument: str) -> float:
        return 1000.0 if instrument.endswith("JPY") else 100000.0

    def _get(self, url: str) -> bytes | None:
        last_error: Exception | None = None
        started = time.monotonic()
        for attempt in range(1, self.retries + 1):
            attempt_started = time.monotonic()
            try:
                _LOG.info("Dukascopy download start attempt=%d/%d url=%s", attempt, self.retries, url)
                response = self.session.get(url, timeout=(8, self.timeout))
                elapsed = time.monotonic() - attempt_started
                if response.status_code == 404:
                    _LOG.info("Dukascopy file missing (normal for non-trading period) elapsed=%.2fs url=%s", elapsed, url)
                    return None
                if response.status_code in {429, 500, 502, 503, 504}:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else min(2.0 ** (attempt - 1), 15.0)
                    except ValueError:
                        delay = min(2.0 ** (attempt - 1), 15.0)
                    last_error = RuntimeError(f"HTTP {response.status_code}")
                    _LOG.warning(
                        "Dukascopy transient HTTP %s attempt=%d/%d elapsed=%.2fs retry_in=%.1fs",
                        response.status_code, attempt, self.retries, elapsed, delay,
                    )
                    if attempt < self.retries:
                        time.sleep(delay)
                    continue
                response.raise_for_status()
                payload = response.content
                _LOG.info(
                    "Dukascopy download complete attempt=%d/%d bytes=%d elapsed=%.2fs url=%s",
                    attempt, self.retries, len(payload), elapsed, url,
                )
                return payload
            except requests.RequestException as exc:
                elapsed = time.monotonic() - attempt_started
                last_error = exc
                _LOG.warning(
                    "Dukascopy request error attempt=%d/%d elapsed=%.2fs error=%s",
                    attempt, self.retries, elapsed, exc,
                )
                if attempt < self.retries:
                    time.sleep(min(2.0 ** (attempt - 1), 15.0))
        total = time.monotonic() - started
        raise RuntimeError(
            f"Dukascopy request failed after {self.retries} attempts "
            f"({total:.1f}s): {last_error}"
        )

    def _decode_ohlc(self, payload: bytes, instrument: str, period_start: datetime) -> pd.DataFrame:
        if not payload:
            return self._empty()
        try:
            raw = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
        except lzma.LZMAError as exc:
            raise RuntimeError(f"Unable to decode Dukascopy .bi5 data: {exc}") from exc

        record_size = 24
        if len(raw) % record_size:
            raise RuntimeError(
                f"Malformed Dukascopy candle payload: {len(raw)} bytes is not a multiple of {record_size}"
            )

        scale = self._scale(instrument)
        rows = []
        for offset in range(0, len(raw), record_size):
            seconds, open_raw, close_raw, low_raw, high_raw, volume = struct.unpack(
                ">IIIII f", raw[offset:offset + record_size]
            )
            ts = period_start + pd.to_timedelta(seconds, unit="s").to_pytimedelta()
            rows.append((ts, open_raw / scale, high_raw / scale, low_raw / scale, close_raw / scale, float(volume)))

        if not rows:
            return self._empty()

        frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
        frame.index = pd.DatetimeIndex(frame.index, tz="UTC")
        frame = frame.sort_index()
        if frame[["open", "high", "low", "close"]].isna().any().any():
            raise RuntimeError(f"Decoded Dukascopy {instrument} data contains NaN OHLC values")
        return frame

    def _fetch_h1_month(self, instrument: str, year: int, month: int) -> pd.DataFrame:
        symbol = _DUKA_SYMBOLS[instrument]
        url = f"{self.BASE_URL}/{symbol}/{year}/{month - 1:02d}/BID_candles_hour_1.bi5"
        payload = self._get(url)
        if payload is None:
            return self._empty()
        frame = self._decode_ohlc(payload, instrument, datetime(year, month, 1, tzinfo=timezone.utc))
        _LOG.info("Dukascopy H1 month ready %s %04d-%02d rows=%d", instrument, year, month, len(frame))
        return frame

    def _fetch_d1_year(self, instrument: str, year: int) -> pd.DataFrame:
        symbol = _DUKA_SYMBOLS[instrument]
        url = f"{self.BASE_URL}/{symbol}/{year}/BID_candles_day_1.bi5"
        payload = self._get(url)
        if payload is None:
            return self._empty()
        frame = self._decode_ohlc(payload, instrument, datetime(year, 1, 1, tzinfo=timezone.utc))
        _LOG.info("Dukascopy D1 year ready %s %04d rows=%d", instrument, year, len(frame))
        return frame

    @staticmethod
    def _concat_nonempty(frames: list[pd.DataFrame]) -> pd.DataFrame:
        nonempty = [frame for frame in frames if not frame.empty]
        if not nonempty:
            return pd.DataFrame(columns=_COLUMNS)
        return pd.concat(nonempty)

    @staticmethod
    def _validate_result(frame: pd.DataFrame, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        if frame.empty:
            raise RuntimeError(
                f"Dukascopy returned no candles for {instrument}/{timeframe} between {start.isoformat()} and {end.isoformat()}"
            )
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        if not frame.index.is_monotonic_increasing:
            raise RuntimeError(f"Dukascopy {instrument}/{timeframe} timestamps are not monotonic")
        if frame.index.min() < start or frame.index.max() >= end:
            raise RuntimeError(f"Dukascopy {instrument}/{timeframe} returned out-of-range candles")
        _LOG.info(
            "Dukascopy validated %s/%s rows=%d first=%s last=%s",
            instrument, timeframe, len(frame), frame.index.min().isoformat(), frame.index.max().isoformat(),
        )
        return frame

    def candles(self, instrument: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        instrument = instrument.upper()
        timeframe = timeframe.upper()
        if instrument not in _DUKA_SYMBOLS:
            raise ValueError(f"Unsupported FX instrument: {instrument}")
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)
        if end <= start:
            raise ValueError("end must be after start")

        started = time.monotonic()
        _LOG.info(
            "Dukascopy candles start instrument=%s timeframe=%s start=%s end=%s",
            instrument, timeframe, start.isoformat(), end.isoformat(),
        )

        if timeframe in {"H1", "H4"}:
            months = pd.period_range(
                start=start.date().replace(day=1),
                end=end.date().replace(day=1),
                freq="M",
            )
            frames = []
            for index, p in enumerate(months, start=1):
                frames.append(self._fetch_h1_month(instrument, p.year, p.month))
                _LOG.info(
                    "Dukascopy candles progress %s/%s month=%04d-%02d completed=%d/%d",
                    instrument, timeframe, p.year, p.month, index, len(months),
                )
            frame = self._concat_nonempty(frames)
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            if timeframe == "H4":
                frame = (
                    frame.resample("4h", label="left", closed="left")
                    .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
                    .dropna(subset=["open", "high", "low", "close"])
                )
            frame = frame[(frame.index >= start) & (frame.index < end)]
        elif timeframe == "D1":
            years = list(range(start.year, end.year + 1))
            frames = []
            for index, year in enumerate(years, start=1):
                frames.append(self._fetch_d1_year(instrument, year))
                _LOG.info(
                    "Dukascopy candles progress %s/D1 year=%d completed=%d/%d",
                    instrument, year, index, len(years),
                )
            frame = self._concat_nonempty(frames)
            frame = frame[~frame.index.duplicated(keep="last")].sort_index()
            frame = frame[(frame.index >= start) & (frame.index < end)]
        else:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Use H1, H4, or D1.")

        frame = self._validate_result(frame, instrument, timeframe, start, end)
        _LOG.info(
            "Dukascopy candles finished %s/%s rows=%d elapsed=%.1fs",
            instrument, timeframe, len(frame), time.monotonic() - started,
        )
        return frame


DukascopyProvider = DukascopyFXProvider
YahooFXProvider = DukascopyFXProvider
BiquoteFXProvider = DukascopyFXProvider
