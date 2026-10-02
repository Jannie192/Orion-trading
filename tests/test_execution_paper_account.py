from datetime import datetime, timezone

import pytest

from orion_trading.execution import OrderRequest
from orion_trading.execution_paper_account import PaperAccountExecution
from orion_trading.models import Direction


def test_adapter_opens_and_marks_paper_position():
    adapter = PaperAccountExecution()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = adapter.submit(OrderRequest(
        instrument="BTCUSDT",
        direction=Direction.LONG,
        units=2,
        entry=100,
        stop=95,
        target=110,
        client_order_id="paper-1",
        created_at=now,
    ))

    assert result.accepted
    assert adapter.snapshot()["open_orders"] == 1

    closed = adapter.mark_bar("BTCUSDT", high=111, low=101, close=108, at=now)
    assert len(closed) == 1
    assert closed[0].reason == "target"
    assert adapter.snapshot()["equity"] == pytest.approx(10020)


def test_adapter_requires_target():
    adapter = PaperAccountExecution()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    result = adapter.submit(OrderRequest(
        instrument="BTCUSDT",
        direction=Direction.LONG,
        units=1,
        entry=100,
        stop=95,
        target=None,
        client_order_id="paper-2",
        created_at=now,
    ))

    assert not result.accepted
    assert result.reason == "TARGET_REQUIRED"
