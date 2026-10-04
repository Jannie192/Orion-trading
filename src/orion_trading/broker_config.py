from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class BrokerSelection:
    adapter: str = "paper"
    mode: str = "paper"
    live_enabled: bool = False


def broker_selection() -> BrokerSelection:
    adapter = os.getenv("ORION_BROKER_ADAPTER", "paper").strip().lower()
    mode = os.getenv("ORION_EXECUTION_MODE", "paper").strip().lower()
    live_enabled = os.getenv("ORION_LIVE_TRADING_ENABLED", "false").strip().lower() == "true"
    if mode != "live":
        live_enabled = False
    return BrokerSelection(adapter=adapter, mode=mode, live_enabled=live_enabled)


def live_trading_is_locked() -> bool:
    selection = broker_selection()
    return not (selection.mode == "live" and selection.live_enabled)
