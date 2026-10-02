from __future__ import annotations

from datetime import datetime
import pandas as pd

try:
    import dukascopy_python as dukas
    from dukascopy_python import instruments as dukas_instruments
except ImportError:
    dukas = None
    dukas_instruments = None

TIMEFRAMES = {
    "M15": ("INTERVAL_MIN_15", "INTERVAL_MINUTE_15", "INTERVAL_M15"),
    "H1": ("INTERVAL_HOUR_1", "INTERVAL_H1"),
    "H4": ("INTERVAL_HOUR_4", "INTERVAL_H4"),
    "D1": ("INTERVAL_DAY_1", "INTERVAL_D1"),
}

INSTRUMENTS = {
    "EUR_USD": "EUR/USD",
    "GBP_USD": "GBP/USD",
    "USD_JPY": "USD/JPY",
    "USD_CHF": "USD/CHF",
    "AUD_USD": "AUD/USD",
    "USD_CAD": "USD/CAD",
    "NZD_USD": "NZD/USD",
}


def _constant(prefixes: tuple[str, ...], value: str | None = None):
    if dukas is None:
        raise RuntimeError("dukascopy-python is not installed")
    for name in prefixes:
        candidate = getattr(dukas, name, None)
        if candidate is not None:
            return candidate
    if value is not None and dukas_instruments is not None:
        for name, candidate in vars(dukas_instruments).items():
            if name.startswith("INSTRUMENT_") and candidate == value:
                return candidate
    raise RuntimeError(f"Dukascopy constant not found: {prefixes}")


def _instrument(symbol: str):
    value = INSTRUMENTS.get(symbol, symbol)
    if dukas_instruments is None:
        raise RuntimeError("dukascopy-python instruments module is unavailable")
    for name, candidate in vars(dukas_instruments).items():
        if name.startswith("INSTRUMENT_") and candidate == value:
            return candidate
    raise ValueError(f"Unsupported Dukascopy instrument: {symbol} ({value})")


def _interval(timeframe: str):
    candidates = TIMEFRAMES.get(timeframe)
    if candidates is None:
        raise ValueError(f"Unsupported Dukascopy timeframe: {timeframe}")
    return _constant(candidates)


class DukascopyClient:
    """Broker-independent historical-data adapter backed by Dukascopy's public feed."""

    def __init__(self):
        if dukas is None:
            raise RuntimeError(
                "dukascopy-python is not installed. Install the [dukascopy] extra."
            )

    def close(self) -> None:
        return None

    def candles(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        start = (start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")).to_pydatetime()
        end = (end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")).to_pydatetime()

        frame = dukas.fetch(
            _instrument(instrument),
            _interval(timeframe),
            dukas.OFFER_SIDE_BID,
            start,
            end,
        )

        if frame is None or frame.empty:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], tz="UTC", name="timestamp"),
            )

        frame = frame.copy()
        if "timestamp" in frame.columns:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
            frame = frame.set_index("timestamp")
        else:
            frame.index = pd.to_datetime(frame.index, utc=True)

        frame.index.name = "timestamp"
        frame = frame.sort_index()
        frame = frame[~frame.index.duplicated(keep="last")]

        columns = ["open", "high", "low", "close"]
        if "volume" in frame.columns:
            columns.append("volume")
        else:
            frame["volume"] = 0.0
            columns.append("volume")

        return frame[columns].astype(float)
