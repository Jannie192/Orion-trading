from __future__ import annotations

import math
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
        self.service_role_key = service_role_key or os.getenv("ORION_SUPABASE_SERVICE_ROLE_KEY", "")
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
            batch = rows[start:start + self.batch_size]
            response = requests.post(endpoint, headers=self._headers, json=batch, timeout=self.timeout)
            if not response.ok:
                raise RuntimeError(f"Supabase candle upsert failed ({response.status_code}): {response.text[:500]}")

    def save(self, instrument: str, timeframe: str, frame: pd.DataFrame, provider: str) -> int:
        if frame.empty:
            return 0
        normalized = frame.sort_index().copy()
        idx = pd.DatetimeIndex(normalized.index)
        idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
        normalized.index = idx
        normalized = normalized[~normalized.index.duplicated(keep="last")]
        rows: list[dict] = []
        for timestamp, row in normalized.iterrows():
            rows.append({
                "instrument": instrument,
                "timeframe": timeframe.upper(),
                "ts": timestamp.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
                "provider": provider,
            })
        self._upsert_rows(rows)
        return len(rows)

    def load(
        self,
        instrument: str,
        timeframe: str,
        start_at: str | None = None,
        end_at: str | None = None,
        limit: int = 10000,
        provider: str | None = None,
    ) -> pd.DataFrame:
        if limit <= 0:
            raise ValueError("limit must be positive")
        params = {
            "instrument": f"eq.{instrument}",
            "timeframe": f"eq.{timeframe.upper()}",
            "order": "ts.asc",
            "limit": str(limit),
        }
        if provider:
            params["provider"] = f"eq.{provider}"
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
            raise RuntimeError(f"Supabase candle query failed ({response.status_code}): {response.text[:500]}")
        rows = response.json()
        if not rows:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([], tz="UTC"))
        frame = pd.DataFrame(rows)
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame = frame.set_index("ts").sort_index()
        return frame[["open", "high", "low", "close", "volume"]].astype(float)

    def record_research_result(self, *, strategy_name: str, strategy_version: str, result, start_at: str, end_at: str) -> str:
        endpoint = f"{self.url}/rest/v1/research_runs"
        backtest = result.backtest
        profit_factor_infinite = math.isinf(backtest.profit_factor)
        payload = {
            "strategy_name": strategy_name, "strategy_version": strategy_version,
            "instrument": result.instrument, "timeframe": result.timeframe.upper(),
            "start_at": start_at, "end_at": end_at, "data_rows": result.data_rows,
            "data_downloaded": result.data_downloaded, "gaps_filled": result.gaps_filled,
            "initial_equity": backtest.initial_equity, "final_equity": backtest.final_equity,
            "total_return_pct": backtest.total_return_pct, "max_drawdown_pct": backtest.max_drawdown_pct,
            "trade_count": len(backtest.trades), "wins": backtest.wins, "losses": backtest.losses,
            "win_rate_pct": backtest.win_rate_pct,
            "profit_factor": None if profit_factor_infinite else backtest.profit_factor,
            "profit_factor_infinite": profit_factor_infinite,
        }
        response = requests.post(endpoint, headers={**self._headers, "Prefer": "return=representation"}, json=payload, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Supabase research result record failed ({response.status_code}): {response.text[:500]}")
        rows = response.json()
        if not rows or not rows[0].get("run_id"):
            raise RuntimeError("Supabase research result did not return run_id")
        return str(rows[0]["run_id"])

    def record_strategy_experiment(self, *, experiment, days: int = 0, validation: dict | None = None) -> str:
        from .strategy_experiments import serialise_experiment
        strategy_endpoint = f"{self.url}/rest/v1/strategy_versions"
        lookup_params = {
            "name": f"eq.{experiment.strategy_name}",
            "version": f"eq.{experiment.strategy_version}",
            "instrument": f"eq.{experiment.instrument}",
            "timeframe": f"eq.{experiment.timeframe.upper()}",
            "limit": "1",
        }
        response = requests.get(strategy_endpoint, headers=self._headers, params=lookup_params, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Supabase strategy version lookup failed ({response.status_code}): {response.text[:500]}")
        existing = response.json()
        if existing:
            strategy_id = existing[0]["strategy_id"]
        else:
            payload = {
                "name": experiment.strategy_name, "version": experiment.strategy_version,
                "instrument": experiment.instrument, "timeframe": experiment.timeframe.upper(),
                "days": days,
                "risks": str(experiment.best.parameters.get("risk_per_trade_pct", "") if experiment.best else ""),
                "stops": str(experiment.best.parameters.get("atr_stop_multiple", "") if experiment.best else ""),
                "rewards": str(experiment.best.parameters.get("reward_multiple", "") if experiment.best else ""),
                "status": "DRAFT",
            }
            response = requests.post(strategy_endpoint, headers={**self._headers, "Prefer": "return=representation"}, json=payload, timeout=self.timeout)
            if not response.ok:
                raise RuntimeError(f"Supabase strategy version create failed ({response.status_code}): {response.text[:500]}")
            rows = response.json()
            if not rows or not rows[0].get("strategy_id"):
                raise RuntimeError("Supabase strategy version did not return strategy_id")
            strategy_id = rows[0]["strategy_id"]

        experiment_endpoint = f"{self.url}/rest/v1/strategy_experiments"
        serialised = serialise_experiment(experiment)
        if validation is not None:
            serialised["validation"] = validation
        grid = {
            key: sorted({variant.parameters[key] for variant in experiment.variants if key in variant.parameters})
            for key in (experiment.variants[0].parameters.keys() if experiment.variants else ())
        }
        payload = {
            "strategy_id": strategy_id, "strategy_name": experiment.strategy_name,
            "strategy_version": experiment.strategy_version, "instrument": experiment.instrument,
            "timeframe": experiment.timeframe.upper(), "days": days, "grid": grid,
            "validation": {"variant_count": experiment.variant_count, "selection_rule": "score_then_return_then_drawdown_then_trade_count"},
            "results": serialised,
        }
        response = requests.post(experiment_endpoint, headers={**self._headers, "Prefer": "return=representation"}, json=payload, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Supabase strategy experiment record failed ({response.status_code}): {response.text[:500]}")
        rows = response.json()
        if not rows or not rows[0].get("experiment_id"):
            raise RuntimeError("Supabase strategy experiment did not return experiment_id")
        return str(rows[0]["experiment_id"])

    def promote_paper_candidate(self, *, experiment, experiment_id: str, validation: dict, days: int = 0) -> str:
        if (validation.get("approval") or {}).get("status") != "PASS":
            raise ValueError("only validation with approval status PASS can be promoted")
        candidate = validation.get("validated_candidate")
        if not candidate or not candidate.get("parameters"):
            raise ValueError("validation does not contain a validated candidate")
        strategy_endpoint = f"{self.url}/rest/v1/strategy_versions"
        lookup_params = {
            "name": f"eq.{experiment.strategy_name}",
            "version": f"eq.{experiment.strategy_version}",
            "instrument": f"eq.{experiment.instrument}",
            "timeframe": f"eq.{experiment.timeframe.upper()}",
            "limit": "1",
        }
        response = requests.get(strategy_endpoint, headers=self._headers, params=lookup_params, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Supabase paper candidate lookup failed ({response.status_code}): {response.text[:500]}")
        rows = response.json()
        if not rows:
            raise RuntimeError("Supabase paper candidate requires an existing strategy version")
        strategy_id = rows[0]["strategy_id"]
        parameters = {str(key): float(value) for key, value in candidate["parameters"].items()}
        payload = {
            "status": "PAPER_CANDIDATE", "days": days,
            "risks": str(parameters.get("risk_per_trade_pct", "")),
            "stops": str(parameters.get("atr_stop_multiple", "")),
            "rewards": str(parameters.get("reward_multiple", "")),
            "candidate_parameters": parameters, "validation": validation,
            "source_experiment_id": experiment_id,
        }
        response = requests.patch(f"{strategy_endpoint}?strategy_id=eq.{strategy_id}", headers={**self._headers, "Prefer": "return=representation"}, json=payload, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Supabase paper candidate promotion failed ({response.status_code}): {response.text[:500]}")
        rows = response.json()
        if not rows or not rows[0].get("strategy_id"):
            raise RuntimeError("Supabase paper candidate promotion did not return strategy_id")
        return str(rows[0]["strategy_id"])

    def record_dataset(self, *, provider: str, instrument: str, timeframe: str, start_at: str, end_at: str, row_count: int, missing_bars: int, sha256: str, quality_passed: bool, artifact_path: str | None = None) -> None:
        endpoint = f"{self.url}/rest/v1/market_data_datasets"
        payload = {
            "provider": provider, "instrument": instrument, "timeframe": timeframe.upper(),
            "start_at": start_at, "end_at": end_at, "row_count": row_count,
            "missing_bars": missing_bars, "sha256": sha256, "quality_passed": quality_passed,
            "artifact_path": artifact_path,
        }
        response = requests.post(endpoint, headers={**self._headers, "Prefer": "return=minimal"}, json=payload, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Supabase dataset record failed ({response.status_code}): {response.text[:500]}")
