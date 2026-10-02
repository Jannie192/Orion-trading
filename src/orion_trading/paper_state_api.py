from __future__ import annotations

from dataclasses import asdict
from .paper_runner import PaperRunner


class PaperStateAdapter:
    """Exposes paper-runner state as dashboard-safe JSON data."""

    def __init__(self, runner: PaperRunner | None = None) -> None:
        self.runner = runner or PaperRunner()

    def snapshot(self) -> dict:
        account = self.runner.account.snapshot()
        performance = self.runner.performance()
        return {
            "mode": "paper",
            "live_trading_enabled": False,
            "account": account,
            "performance": asdict(performance),
            "open_positions": [
                {
                    "order_id": o.order_id,
                    "instrument": o.instrument,
                    "direction": o.direction,
                    "units": o.units,
                    "entry": o.entry,
                    "stop": o.stop,
                    "target": o.target,
                    "created_at": o.created_at.isoformat(),
                }
                for o in self.runner.account.orders.values()
            ],
        }
