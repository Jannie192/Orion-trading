from __future__ import annotations

import os
from typing import Any
import requests


class SupabaseStrategyStore:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    
    @property
    def headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs: Any) -> list[dict[str, Any]]:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        response = requests.request(method, f"{self.url}/rest/v1/{path}", headers=headers, timeout=15, **kwargs)
        if not response.ok:
            raise RuntimeError(f"Supabase request failed ({response.status_code}): {response.text[:500]}")
        return response.json() if response.content else []

    def versions(self) -> list[dict[str, Any]]:
        return self._request("GET", "strategy_versions?select=*&order=updated_at.desc")

    def experiment(self, experiment_id: str) -> dict[str, Any]:
        rows = self._request("GET", f"strategy_experiments?select=*&experiment_id=eq.{experiment_id}&limit=1")
        if not rows:
            raise ValueError("EXPERIMENT_NOT_FOUND")
        return rows[0]

    def experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._request("GET", f"strategy_experiments?select=*&order=created_at.desc&limit={max(1,min(limit,100))}")

    def create_version(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "strategy_versions", json=payload,
            headers={**self.headers, "Prefer": "return=representation,resolution=merge-duplicates"})
        return rows[0]

    def create_experiment(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "strategy_experiments", json=payload,
            headers={**self.headers, "Prefer": "return=representation"})
        return rows[0]

    def create_insight(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "research_insights", json=payload,
            headers={**self.headers, "Prefer": "return=representation"})
        return rows[0]

    def insights(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._request("GET", f"research_insights?select=*&order=created_at.desc&limit={max(1,min(limit,100))}")

    def create_iteration(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "research_iterations", json=payload,
            headers={**self.headers, "Prefer": "return=representation"})
        return rows[0]

    def iterations(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._request("GET", f"research_iterations?select=*&order=created_at.desc&limit={max(1,min(limit,100))}")

    def iteration(self, iteration_id: str) -> dict[str, Any]:
        rows = self._request("GET", f"research_iterations?select=*&iteration_id=eq.{iteration_id}&limit=1")
        if not rows:
            raise ValueError("ITERATION_NOT_FOUND")
        return rows[0]

    def update_iteration(self, iteration_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("PATCH", f"research_iterations?iteration_id=eq.{iteration_id}",
            json=payload,
            headers={**self.headers, "Prefer": "return=representation"})
        if not rows:
            raise ValueError("ITERATION_NOT_FOUND")
        return rows[0]

    def promote(self, strategy_id: str, status: str) -> dict[str, Any]:
        if status not in {"DRAFT","VALIDATED","PAPER_CANDIDATE","PAPER_ACTIVE"}:
            raise ValueError("INVALID_STRATEGY_STATUS")
        rows = self._request("PATCH", f"strategy_versions?strategy_id=eq.{strategy_id}",
            json={"status": status},
            headers={**self.headers, "Prefer": "return=representation"})
        if not rows:
            raise ValueError("STRATEGY_NOT_FOUND")
        return rows[0]
