from datetime import datetime, timezone

from orion_trading.models import Direction
from orion_trading.paper_runner import PaperRunner


def test_runner_applies_risk_before_paper_execution():
    runner = PaperRunner()
    blocked = runner.submit(
        order_id="blocked", instrument="BTCUSDT", direction=Direction.LONG,
        units=1, entry=100, stop=95, target=110, risk_pct=1.0
    )
    assert not blocked.accepted
    assert blocked.reason == "RISK_PER_TRADE_LIMIT"

    accepted = runner.submit(
        order_id="p1", instrument="BTCUSDT", direction=Direction.LONG,
        units=1, entry=100, stop=95, target=110, risk_pct=0.5,
        regime="TREND_UP", signal_type="BREAKOUT",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    assert accepted.accepted


def test_runner_closes_and_journals_trade():
    runner = PaperRunner()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    runner.submit(
        order_id="p1", instrument="BTCUSDT", direction=Direction.LONG,
        units=1, entry=100, stop=95, target=110, risk_pct=0.5,
        regime="TREND_UP", signal_type="BREAKOUT", created_at=now
    )
    closed = runner.on_bar("BTCUSDT", 111, 101, 108, now)
    assert closed[0].reason == "target"
    assert runner.performance().trades == 1
    assert runner.performance().net_pnl == 10
