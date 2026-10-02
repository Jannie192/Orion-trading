from orion_trading.paper_state_api import PaperStateAdapter


def test_state_adapter_is_dashboard_safe():
    state = PaperStateAdapter().snapshot()
    assert state["mode"] == "paper"
    assert state["live_trading_enabled"] is False
    assert state["account"]["equity"] == 10000
    assert state["performance"]["trades"] == 0
    assert state["open_positions"] == []
