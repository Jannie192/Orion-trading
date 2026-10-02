from datetime import datetime, timezone

from orion_trading.paper_signal_service import PaperSignalService
from orion_trading.signals import SignalCandidate
from orion_trading.models import Direction, Regime


class FakeStore:
    def __init__(self):
        self.orders = {}
        self.trades = []
        self.account_data = {"initial_equity": 10000}

    def has_order(self, order_id):
        return order_id in self.orders

    def account(self):
        return self.account_data

    def closed_trades(self):
        return self.trades

    def create_order(self, order):
        self.orders[order["order_id"]] = order
        return order


def candidate(valid=True):
    return SignalCandidate(
        instrument="BTCUSDT",
        detected_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        regime=Regime.TRENDING,
        direction=Direction.LONG,
        opportunities=[],
        evidence={"test": True},
        entry=100.0,
        stop=95.0,
        target=110.0,
        valid=valid,
        rejection_reason=None if valid else "REJECTED",
    )


def test_valid_candidate_creates_paper_order():
    store = FakeStore()
    result = PaperSignalService(store).submit(candidate(), "H1")
    assert result.accepted
    order = next(iter(store.orders.values()))
    assert order["direction"] == "long"
    assert order["units"] == 10.0


def test_duplicate_candidate_is_rejected():
    store = FakeStore()
    service = PaperSignalService(store)
    first = service.submit(candidate(), "H1")
    second = service.submit(candidate(), "H1")
    assert first.accepted
    assert not second.accepted
    assert second.reason == "DUPLICATE_SIGNAL"


def test_invalid_candidate_is_rejected():
    store = FakeStore()
    result = PaperSignalService(store).submit(candidate(False), "H1")
    assert not result.accepted
    assert result.reason == "REJECTED"
