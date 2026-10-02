from datetime import datetime, timezone

from orion_trading.models import Direction
from orion_trading.paper_trading_service import PaperTradingService


def test_service_accepts_plan_and_closes_target():
    service = PaperTradingService()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    decision = service.submit_plan("BTCUSDT", Direction.LONG, 1, 100, 95, 110, now, "p1")
    assert decision.accepted
    assert service.snapshot()["open_orders"] == 1

    closed = service.on_bar("BTCUSDT", 111, 101, 108, now)
    assert closed[0].reason == "target"
    assert service.snapshot()["equity"] == 10010


def test_service_rejects_neutral():
    service = PaperTradingService()
    decision = service.submit_plan("BTCUSDT", Direction.NEUTRAL, 1, 100, 95, 110)
    assert not decision.accepted
    assert decision.reason == "INVALID_DIRECTION"
