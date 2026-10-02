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
        self.session.headers.update(
            {"Authorization": f"Bearer {config.token}", "Content-Type": "application/json"}
        )

    def candles(
        self,
        instrument: str,
        granularity: str = "M15",
        count: int = 500,
        price: str = "MBA",
        from_time: str | None = None,
        to_time: str | None = None,
        include_first: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "granularity": granularity,
            "price": price,
            "includeFirst": str(include_first).lower(),
        }
        if from_time is not None or to_time is not None:
            if from_time is not None:
                params["from"] = from_time
            if to_time is not None:
                params["to"] = to_time
        else:
            params["count"] = count
        response = self.session.get(
            f"{self.config.base_url}/v3/instruments/{instrument}/candles",
            params=params,
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
