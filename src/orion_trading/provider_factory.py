from __future__ import annotations

import os

from .market_data import MarketDataAdapter


def provider_from_env() -> MarketDataAdapter:
    provider = os.getenv("ORION_DATA_PROVIDER", "oanda").lower()
    if provider == "mt5":
        from .mt5_client import MT5Client
        client = MT5Client()
        client.connect()
        return client
    if provider == "oanda":
        from .oanda_client import OandaClient
        return OandaClient.from_env()
    raise ValueError(f"Unsupported ORION_DATA_PROVIDER={provider!r}")
