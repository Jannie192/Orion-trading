from orion_trading.trade_journal import JournalTrade, TradeJournal


def trade(i, pnl, instrument="BTCUSDT", regime="TREND_UP"):
    return JournalTrade(str(i), instrument, "long", 100, 100 + pnl, 1, pnl, 10, "target" if pnl > 0 else "stop", regime, "TREND_CONTINUATION")


def test_snapshot_metrics():
    journal = TradeJournal()
    for t in [trade(1, 20), trade(2, -10), trade(3, -10), trade(4, 30)]:
        journal.record(t)
    s = journal.snapshot()
    assert s.trades == 4
    assert s.wins == 2
    assert s.win_rate_pct == 50
    assert s.net_pnl == 30
    assert s.profit_factor == 2.5
    assert s.expectancy_r == 0.75
    assert s.max_consecutive_losses == 2


def test_grouped_performance():
    journal = TradeJournal()
    journal.record(trade(1, 20, "BTCUSDT"))
    journal.record(trade(2, -10, "ETHUSDT"))
    groups = journal.grouped("instrument")
    assert groups["BTCUSDT"].net_pnl == 20
    assert groups["ETHUSDT"].losses == 1
