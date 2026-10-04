from __future__ import annotations

from dataclasses import dataclass

from .broker_config import BrokerSelection, broker_selection
from .execution import ExecutionAdapter, PaperExecution


@dataclass(frozen=True)
class BrokerStatus:
    adapter: str
    mode: str
    connected: bool
    live_enabled: bool
    live_locked: bool
    reason: str


class BrokerManager:
    """Single broker-selection boundary for Orion execution.

    Paper is always available. MT5 is opt-in and remains locked unless the
    execution configuration explicitly enables live trading.
    """

    def __init__(self, selection: BrokerSelection | None = None) -> None:
        self.selection = selection or broker_selection()
        self.adapter: ExecutionAdapter = PaperExecution()
        self.status_reason = "PAPER_DEFAULT"

    def initialize(self) -> ExecutionAdapter:
        name = self.selection.adapter
        if name in {"paper", "simulation"}:
            self.adapter = PaperExecution()
            self.status_reason = "PAPER_READY"
            return self.adapter

        if name == "mt5":
            from .mt5_execution import MT5Execution

            self.adapter = MT5Execution(
                login=None,
                password=None,
                server=None,
                terminal_path=None,
                live_enabled=self.selection.live_enabled and self.selection.mode == "live",
            )
            self.status_reason = "MT5_CONFIGURED"
            return self.adapter

        raise ValueError(f"Unsupported broker adapter: {name}")

    def health(self) -> BrokerStatus:
        locked = not (
            self.selection.mode == "live" and self.selection.live_enabled
        )
        try:
            connected = bool(self.adapter.health_check())
        except Exception:
            connected = False

        return BrokerStatus(
            adapter=self.selection.adapter,
            mode=self.selection.mode,
            connected=connected,
            live_enabled=self.selection.live_enabled,
            live_locked=locked,
            reason=self.status_reason,
        )


def create_broker_manager() -> BrokerManager:
    manager = BrokerManager()
    manager.initialize()
    return manager
