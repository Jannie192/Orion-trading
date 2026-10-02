from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class OandaConfig:
    account_id: str
    token: str
    practice: bool = True

    @property
    def base_url(self) -> str:
        return "https://api-fxpractice.oanda.com" if self.practice else "https://api-fxtrade.oanda.com"


class OandaClient:
    """Thin HTTP client. Live mode is opt-in and disabled by default."""

    def __init__(self, config: OandaConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"})

    def candles(self, instrument: str, granularity: str = "M15", count: int = 500) -> dict[str, Any]:
        response = self.session.get(
            f"{self.config.base_url}/v3/instruments/{instrument}/candles",
            params={"granularity": granularity, "count": count, "price": "MBA"},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def account_summary(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.config.base_url}/v3/accounts/{self.config.account_id}/summary",
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
