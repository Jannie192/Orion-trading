from datetime import datetime, timezone

from orion_trading.execution import OrderRequest, PaperExecution
from orion_trading.models import Direction


def test_paper_execution_accepts_valid_long_order():
    broker = PaperExecution()
    order = OrderRequest(
        instrument="EUR_USD",
        direction=Direction.LONG,
        units=1000,
        entry=1.10,
        stop=1.09,
        target=1.12,
        client_order_id="test-1",
        created_at=datetime.now(timezone.utc),
    )
    result = broker.submit(order)
    assert result.accepted is True
    assert result.order_id == "test-1"
    assert len(broker.orders) == 1


def test_paper_execution_rejects_bad_long_stop():
    broker = PaperExecution()
    order = OrderRequest(
        instrument="EUR_USD",
        direction=Direction.LONG,
        units=1000,
        entry=1.10,
        stop=1.11,
        target=1.12,
        client_order_id="test-2",
        created_at=datetime.now(timezone.utc),
    )
    assert broker.submit(order).reason == "INVALID_LONG_STOP"
