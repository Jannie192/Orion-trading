from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from .oanda_client import OandaClient


_GRANULARITY_MINUTES = {"M15": 15, "H1": 60, "H4": 240, "D": 1440}


@dataclass(frozen=True)
class HistoryConfig:
    chunk_days: int = 20
    price: str = "MBA"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def candles_frame(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candle in payload.get("candles", []):
        row: dict[str, Any] = {
            "time": pd.Timestamp(candle["time"]).tz_convert("UTC") if pd.Timestamp(candle["time"]).tzinfo is not None else pd.Timestamp(candle["time"]).tz_localize("UTC"),
            "volume": candle.get("volume"),
            "complete": candle.get("complete", True),
        }
        for component in ("bid", "ask", "mid"):
            data = candle.get(component)
            if data:
                for field in ("o", "h", "l", "c"):
                    row[f"{component}_{field}"] = float(data[field])
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows).set_index("time").sort_index()
    # Strategy calculations use a single canonical close/OHLC.
    for field in ("o", "h", "l", "c"):
        source = f"mid_{field}"
        if source not in frame:
            source = f"bid_{field}"
        frame[field.replace("o", "open").replace("h", "high").replace("l", "low").replace("c", "close")] = frame[source]
    return frame[~frame.index.duplicated(keep="last")]


def fetch_history(
    client: OandaClient,
    instrument: str,
    granularity: str,
    start: datetime,
    end: datetime,
    config: HistoryConfig | None = None,
) -> pd.DataFrame:
    """Download completed historical candles in bounded, retryable time windows."""
    if granularity not in _GRANULARITY_MINUTES:
        raise ValueError(f"Unsupported research granularity: {granularity}")
    start, end = _utc(start), _utc(end)
    if end <= start:
        raise ValueError("end must be after start")

    cfg = config or HistoryConfig()
    step = timedelta(days=cfg.chunk_days)
    pieces: list[pd.DataFrame] = []
    cursor = start

    while cursor < end:
        chunk_end = min(cursor + step, end)
        payload = client.candles(
            instrument,
            granularity=granularity,
            price=cfg.price,
            from_time=cursor.isoformat().replace("+00:00", "Z"),
            to_time=chunk_end.isoformat().replace("+00:00", "Z"),
            include_first=True,
        )
        frame = candles_frame(payload)
        if not frame.empty:
            pieces.append(frame)
        cursor = chunk_end

    if not pieces:
        return pd.DataFrame()

    out = pd.concat(pieces).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    # Never let an incomplete final candle contaminate research.
    if "complete" in out.columns:
        out = out[out["complete"].fillna(True)]
    return out


def fetch_multi_timeframe_history(
    client: OandaClient,
    instrument: str,
    start: datetime,
    end: datetime,
    config: HistoryConfig | None = None,
) -> dict[str, pd.DataFrame]:
    cfg = config or HistoryConfig()
    return {
        tf: fetch_history(client, instrument, tf, start, end, cfg)
        for tf in ("D", "H4", "H1", "M15")
    }
