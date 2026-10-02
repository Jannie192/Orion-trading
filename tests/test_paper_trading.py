from datetime import datetime, timezone

import pytest

from orion_trading.paper_trading import PaperAccount, PaperOrder

def test_long_target_closes_and_updates_equity():
    account = PaperAccount(10_000)
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
    account.open_order(PaperOrder("o1", "BTCUSDT", "long", 2, 100, 95, 110, opened))
    closed = account.mark_bar("BTCUSDT", 111, 101, 108, opened)
    assert len(closed) == 1
    assert closed[0].reason == "target"
    assert account.equity == 10_020

def test_short_stop_closes_with_loss():
    account = PaperAccount(10_000)
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
    account.open_order(PaperOrder("o2", "BTCUSDT", "short", 2, 100, 105, 90, opened))
    closed = account.mark_bar("BTCUSDT", 106, 99, 103, opened)
    assert closed[0].reason == "stop"
    assert account.equity == 9_990

def test_rejects_invalid_levels():
    account = PaperAccount()
    opened = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        account.open_order(PaperOrder("o3", "BTCUSDT", "long", 1, 100, 110, 120, opened))
