from __future__ import annotations

import os
from typing import Iterable

import pandas as pd
import requests


class SupabaseMarketDataStore:
    """Persistent historical OHLCV store backed by Supabase PostgREST."""

    def __init__(
        self,
        url: str | None = None,
        service_role_key: str | None = None,
        batch_size: int = 500,
        timeout: int = 30,
    ) -> None:
        self.url = (url or os.getenv("ORION_SUPABASE_URL", "")).rstrip("/")
        self.service_role_key = service_role_key or os.getenv(
            "ORION_SUPABASE_SERVICE_ROLE_KEY", ""
        )
        if not self.url:
            raise ValueError("ORION_SUPABASE_URL is required")
        if not self.service_role_key:
            raise ValueError("ORION_SUPABASE_SERVICE_ROLE_KEY is required")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
        self.timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }

    def _upsert_rows(self, rows: list[dict]) -> None:
        endpoint = f"{self.url}/rest/v1/market_data_candles"
        for start in range(0, len(rows), self.batch_size):
            batch = rows[start : start + self.batch_size]
            response = requests.post(
                endpoint,
                headers=self._headers,
                json=batch,
                timeout=self.timeout,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Supabase candle upsert failed ({response.status_code}): "
                    f"{response.text[:500]}"
                )

    def save(
        self,
        instrument: str,
        timeframe: str,
        frame: pd.DataFrame,
        provider: str,
    ) -> int:
        if frame.empty:
            return 0

        normalized = frame.sort_index().copy()
        idx = pd.DatetimeIndex(normalized.index)
        if idx.tz is None:
            idx = idx.tz_localize("UTC")
        else:
            idx = idx.tz_convert("UTC")
        normalized.index = idx
        normalized = normalized[~normalized.index.duplicated(keep="last")]

        rows: list[dict] = []
        for timestamp, row in normalized.iterrows():
            rows.append(
                {
                    "instrument": instrument,
                    "timeframe": timeframe.upper(),
                    "ts": timestamp.isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume", 0.0)),
                    "provider": provider,
                }
            )

        self._upsert_rows(rows)
        return len(rows)

    def load(
        self,
        instrument: str,
        timeframe: str,
        start_at: str | None = None,
        end_at: str | None = None,
        limit: int = 10000,
    ) -> pd.DataFrame:
        """Load persisted candles from Supabase as a UTC-indexed OHLCV frame."""
        if limit <= 0:
            raise ValueError("limit must be positive")
        params = {
            "instrument": f"eq.{instrument}",
            "timeframe": f"eq.{timeframe.upper()}",
            "order": "ts.asc",
            "limit": str(limit),
        }
        if start_at and end_at:
            params["and"] = f"(ts.gte.{start_at},ts.lt.{end_at})"
        elif start_at:
            params["ts"] = f"gte.{start_at}"
        elif end_at:
            params["ts"] = f"lt.{end_at}"

        response = requests.get(
            f"{self.url}/rest/v1/market_data_candles",
            headers=self._headers,
            params=params,
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f"Supabase candle query failed ({response.status_code}): "
                f"{response.text[:500]}"
            )
        rows = response.json()
        if not rows:
            return pd.DataFrame(
                columns=["open", "high", "low", "close", "volume"],
                index=pd.DatetimeIndex([], tz="UTC"),
            )
        frame = pd.DataFrame(rows)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame = frame.set_index("ts").sort_index()
        return frame[["open", "high", "low", "close", "volume"]].astype(float)

    def record_dataset(
        self,
        *,
        provider: str,
        instrument: str,
        timeframe: str,
        start_at: str,
        end_at: str,
        row_count: int,
        missing_bars: int,
        sha256: str,
        quality_passed: bool,
        artifact_path: str | None = None,
    ) -> None:
        endpoint = f"{self.url}/rest/v1/market_data_datasets"
        payload = {
            "provider": provider,
            "instrument": instrument,
            "timeframe": timeframe.upper(),
            "start_at": start_at,
            "end_at": end_at,
            "row_count": row_count,
            "missing_bars": missing_bars,
            "sha256": sha256,
            "quality_passed": quality_passed,
            "artifact_path": artifact_path,
        }
        response = requests.post(
            endpoint,
            headers={**self._headers, "Prefer": "return=minimal"},
            json=payload,
            timeout=self.timeout,
        )
        if not response.ok:
            raise RuntimeError(
                f"Supabase dataset record failed ({response.status_code}): "
                f"{response.text[:500]}"
            )
