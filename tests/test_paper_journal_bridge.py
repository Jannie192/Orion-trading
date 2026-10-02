from datetime import datetime, timezone

from orion_trading.paper_trading import PaperAccount, PaperOrder
from orion_trading.paper_journal_bridge import PaperJournalBridge
from orion_trading.trade_journal import TradeJournal


def test_bridge_syncs_closed_trade_once():
    account = PaperAccount()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    account.open_order(PaperOrder("o1", "BTCUSDT", "long", 1, 100, 95, 110, now))
    closed = account.mark_bar("BTCUSDT", 111, 101, 108, now)
    journal = TradeJournal()
    bridge = PaperJournalBridge(journal)
    assert bridge.sync(closed, {"o1": 5}, {"o1": {"regime": "TREND_UP", "signal_type": "BREAKOUT"}}) == 1
    assert bridge.sync(closed, {"o1": 5}) == 0
    assert journal.snapshot().trades == 1
    assert journal.grouped("regime")["TREND_UP"].wins == 1
